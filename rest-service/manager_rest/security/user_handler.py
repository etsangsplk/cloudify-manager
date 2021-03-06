#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired

from manager_rest.storage import user_datastore


def user_loader(request):
    """Attempt to retrieve the current user from the request
    Either from request's Authorization attribute, or from the token header

    Having this function makes sure that this will work:
    > from flask_security import current_user
    > current_user
    <manager_rest.storage.models.User object at 0x50d9d10>

    :param request: flask's request
    :return: A user object, or None if not found
    """
    if request.authorization:
        user = get_user_from_auth(request.authorization)
    else:
        token = get_token_from_request(request)
        _, _, user, _ = get_token_status(token)
    return user


def get_user_from_auth(auth):
    return user_datastore.get_user(auth.username)


def get_token_from_request(request):
    token_auth_header = current_app.config[
            'SECURITY_TOKEN_AUTHENTICATION_HEADER']
    return request.headers.get(token_auth_header)


def get_token_status(token):
    """Mimic flask_security.utils.get_token_status with some changes

    :param token: The token to decrypt
    :return: A tuple: (expired, invalid, user, data)
    """
    security = current_app.extensions['security']
    serializer = security.remember_token_serializer
    max_age = security.token_max_age

    user, data = None, None
    expired, invalid = False, False

    try:
        data = serializer.loads(token, max_age=max_age)
    except SignatureExpired:
        expired = True
    except (BadSignature, TypeError, ValueError):
        invalid = True

    if data:
        user = user_datastore.find_user(id=data[0])

    return expired, invalid, user, data
