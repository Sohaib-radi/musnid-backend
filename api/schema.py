"""
OpenAPI extensions for the project's own API classes.

Imported by ``ApiConfig.ready()`` so drf-spectacular finds them when it builds
the schema.
"""

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class OptionalJWTScheme(SimpleJWTScheme):
    """
    ``OptionalJWTAuthentication`` is SimpleJWT's bearer scheme, so it reuses ``jwtAuth``.

    Registering a second scheme under that name is a spectacular conflict, and
    a new name would ask Swagger users for the same token twice. So this
    extension registers no scheme (``name = []``) and only references
    ``jwtAuth``, which the default authentication of the other endpoints
    registers. Views using it are ``AllowAny``, so the schema also lists "no
    authentication" as an alternative: the token is optional there too.
    """

    target_class = 'api.authentication.OptionalJWTAuthentication'
    name = []

    def get_security_requirement(self, auto_schema):
        return {SimpleJWTScheme.name: []}
