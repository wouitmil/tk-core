# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
"""
Defines the supported types of authentication methods with Shotgun. You can
either authenticate with a session token with the SessionUser class or with an
api key with the ScriptUser class. This module is meant to be used internally.
"""

import pickle
from .shotgun_wrapper import ShotgunWrapper

from . import session_cache
from .errors import CachingVolatileUserException


_shotgun_instance_factory = ShotgunWrapper
"""
Indirection to create ShotgunWrapper instances. Great for unit testing.
"""


class ShotgunUser(object):
    """
    Abstract base class for a Shotgun user. It tracks the user's host and proxy.
    """
    def __init__(self, host, http_proxy):
        """
        Constructor.

        :param host: Host for this Shotgun user.
        :param http_proxy: HTTP proxy to use with this host.
        """
        self._host = host
        self._http_proxy = http_proxy

    def get_host(self):
        """
        Returns the host for this user.

        :returns: The host string.
        """
        return self._host

    def get_http_proxy(self):
        """
        Returns the HTTP proxy for this user.

        :returns: The HTTP proxy string.
        """
        return self._http_proxy

    def create_sg_connection(self):
        """
        Creates a Shotgun connection using the credentials for this user.

        :raises NotImplementedError: If not overridden in the derived class, 
                                     this method will raise a 
                                     NotImplementedError.
        """
        self.__class__._not_implemented("create_sg_connection")

    def to_dict(self):
        """
        Converts the user into a dictionary object.

        :returns: A dictionary with all the attributes of the user.

        :raises NotImplementedError: If not overridden in the derived class, 
                                     this method will raise a 
                                     NotImplementedError.
        """
        return {
            "http_proxy": self._http_proxy,
            "host": self._host
        }

    @classmethod
    def from_dict(cls, payload):
        """
        Creates a user from a dictionary.

        :param payload: Dictionary with the user information.

        :returns: A ShotgunUser derived instance.

        :raises NotImplementedError: If not overridden in the derived class, 
                                     this method will raise a 
                                     NotImplementedError.

        """
        cls._not_implemented("from_dict")

    @classmethod
    def _not_implemented(cls, method):
        """
        Raise a properly formatted error message when a method is not implemented.

        :param method: Name of the method not implemented.

        :raises NotImplementedError: Thrown with the message "<class-name>.<method-name>
                                     is not implemented."
        """
        raise NotImplementedError(
            "%s.%s is not implemented." % (cls.__name__, method)
        )


class SessionUser(ShotgunUser):
    """
    A user that authenticates to the Shotgun server using a session token.
    """
    def __init__(self, host, login, session_token, http_proxy, is_volatile=False):
        """
        Constructor.

        :param host: Host for this Shotgun user.
        :param login: Login name for the user.
        :param session_token: Session token for the user.
        :param http_proxy: HTTP proxy to use with this host. Defaults to None.
        :param is_volatile: Indicates if the user can cache it's credentials to
                            disk.
        """

        super(SessionUser, self).__init__(host, http_proxy)

        self._login = login
        self._session_token = session_token
        self._is_volatile = is_volatile

    def get_login(self):
        """
        Returns the login name for this user.

        :returns: The login name string.
        """
        return self._login

    def get_session_token(self):
        """
        Returns the session token for this user.

        :returns: The session token string.
        """
        return self._session_token

    def set_session_token(self, session_token):
        """
        Updates the session token for this user.

        :param session_token: The new session token for this user.
        """
        self._session_token = session_token

    def create_sg_connection(self):
        """
        Creates a Shotgun instance using the script user's credentials.

        :returns: A Shotgun instance.
        """
        return _shotgun_instance_factory(
            self._host, session_token=self._session_token, http_proxy=self._http_proxy,
            user=self
        )

    def mark_volatile(self):
        """
        Marks this user as volatile. A volatile user won't save it's credentials to disk.
        """
        self._is_volatile = True

    def is_volatile(self):
        """
        Returns if a user is volatile.

        :returns: True if volatile, False otherwise.
        """
        return self._is_volatile

    def save(self):
        """
        Saves a user's information in the local site cache.

        :param user: Specifying a user to be the current user.

        :raises CachingVolatileUserException: Raised if the user is volatile.
        """
        if self._is_volatile:
            raise CachingVolatileUserException()
        session_cache.cache_session_data(
            self.get_host(),
            self.get_login(),
            self.get_session_token()
        )

    @staticmethod
    def clear_saved_user(host):
        """
        Removes the saved user's credentials from disk for a given host. The
        next time the SessionUser.get_saved_user method is called, None will be
        returned.

        :param host: Host to remove the saved user from.
        """
        session_cache.delete_session_data(host)

    @staticmethod
    def get_saved_user(host, http_proxy):
        """
        Returns the currenly saved user for a given host.

        :param host: Host to retrieve the saved user from.

        :returns: A SessionUser instance if a user was saved, None otherwise.
        """
        credentials = session_cache.get_session_data(host)
        if credentials:
            return SessionUser(
                host=host,
                http_proxy=http_proxy,
                **credentials
            )
        else:
            return None

    @staticmethod
    def from_dict(representation):
        """
        Creates a user from a dictionary.

        :param payload: Dictionary with the user information.

        :returns: A SessionUser instance.
        """

        return SessionUser(**representation)

    def to_dict(self):
        """
        Converts the user into a dictionary object.

        :returns: A dictionary with all the attributes of the user.
        """
        data = super(SessionUser, self).to_dict()
        data["login"] = self._login
        data["session_token"] = self._session_token
        data["is_volatile"] = self._is_volatile
        return data


class ScriptUser(ShotgunUser):
    """
    User that authenticates to the Shotgun server using a api name and api key.
    """
    def __init__(self, host, api_script, api_key, http_proxy):
        """
        Constructor.

        :param host: Host for this Shotgun user.
        :param api_script: API script name.
        :param api_key: API script key.
        :param http_proxy: HTTP proxy to use with this host. Defaults to None.
        """
        super(ScriptUser, self).__init__(host, http_proxy)

        self._api_script = api_script
        self._api_key = api_key

    def create_sg_connection(self):
        """
        Creates a Shotgun instance using the script user's credentials.

        :returns: A Shotgun instance.
        """
        return _shotgun_instance_factory(
            self._host,
            script_name=self._api_script,
            api_key=self._api_key,
            http_proxy=self._http_proxy,
            user=self
        )

    def get_script(self):
        """
        Returns the script user name.

        :returns: The script user name.
        """
        return self._api_script

    def get_key(self):
        """
        Returns the script user key.

        :returns: The script user key.
        """
        return self._api_key

    def to_dict(self):
        """
        Converts the user into a dictionary object.

        :returns: A dictionary with all the attributes of the user.
        """
        data = super(ScriptUser, self).to_dict()
        data["api_script"] = self._api_script
        data["api_key"] = self._api_key
        return data

    @staticmethod
    def from_dict(representation):
        """
        Creates a user from a dictionary.

        :param payload: Dictionary with the user information.

        :returns: A ScriptUser instance.
        """
        return ScriptUser(**representation)


def is_script_user(user):
    """
    Indicates if the user is a script user.

    :param user: A ShotgunUser derived instance.

    :returns: True is user is an instance of ScriptUser, False otherwise.
    """
    return isinstance(user, ScriptUser)


def is_session_user(user):
    """
    Indicates if the user is a session user.

    :param user: A ShotgunUser derived instance.

    :returns: True is user is an instance of SessionUser, False otherwise.
    """
    return isinstance(user, SessionUser)


__factories = {
    # LoginPassword-like-User should go here in we ever implement it.
    SessionUser.__name__: SessionUser.from_dict,
    ScriptUser.__name__: ScriptUser.from_dict
}


def serialize(user):
    """
    Serializes a user. Meant to be consumed by deserialize.

    :param user: User object that needs to be serialized.

    :returns: The payload representing the user.
    """
    # Pickle the dictionary and inject the user type in the payload so we know
    # how to unpickle the user.
    return pickle.dumps({
        "type": user.__class__.__name__,
        "data": user.to_dict()
    })


def deserialize(payload):
    """
    Converts a payload produced by serialize into any of the ShotgunUser
    derived instance.

    :params payload: Pickled dictionary of values

    :returns: A ShotgunUser derived instance.
    """
    # Unpickle the dictionary
    user_dict = pickle.loads(payload)

    # Find which user type we have
    global __factories
    factory = __factories.get(user_dict["type"])
    # Unknown representation, something is wrong. Maybe backward compatible code broke?
    if not factory:
        raise Exception("Invalid user representation: %s" % user_dict)
    # Instantiate the user object.
    return factory(user_dict["data"])