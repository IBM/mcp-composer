import pytest
from mcp_composer.utils import ServerConfigValidator
from mcp_composer.utils import ConfigKey, MemberServerType, ValidationError


class TestGraphQLConfigValidation:
    def test_valid_graphql_config_passes(self):
        config = {
           str(ConfigKey.ID): "graphql-test",
            ConfigKey.TYPE: MemberServerType.GRAPHQL,
            ConfigKey.GRAPHQL: {
                ConfigKey.ENDPOINT: "https://example.com/graphql",
                ConfigKey.SCHEMA_FILEPATH: "schemas/schema.graphql"
            }
        }
        validator = ServerConfigValidator(config)
        # Should not raise
        validator.validate_graphql_config()

    def test_missing_graphql_section_raises(self):
        config = {
            str(ConfigKey.ID): "graphql-missing-section",
            ConfigKey.TYPE: MemberServerType.GRAPHQL,
        }
        validator = ServerConfigValidator(config)
        with pytest.raises(ValidationError) as exc:
            validator.validate_graphql_config()
            print(exc.value)
            assert ConfigKey.GRAPHQL in str(exc.value)

    def test_missing_endpoint_raises(self):
        config = {
            str(ConfigKey.ID): "graphql-no-endpoint",
            ConfigKey.TYPE: MemberServerType.GRAPHQL,
            ConfigKey.GRAPHQL: {
                ConfigKey.SCHEMA_FILEPATH: "schemas/schema.graphql"
            }
        }
        validator = ServerConfigValidator(config)
        with pytest.raises(ValidationError) as exc:
            validator.validate_graphql_config()
            assert ConfigKey.ENDPOINT in str(exc.value)

    def test_missing_schema_filepath_raises(self):
        config = {
            str(ConfigKey.ID): "graphql-no-schema",
            ConfigKey.TYPE: MemberServerType.GRAPHQL,
            ConfigKey.GRAPHQL: {
                ConfigKey.ENDPOINT: "https://example.com/graphql"
            }
        }
        validator = ServerConfigValidator(config)
        with pytest.raises(ValidationError) as exc:
            validator.validate_graphql_config()
            assert ConfigKey.SCHEMA_FILEPATH in str(exc.value)

    def test_non_graphql_config_does_not_trigger_graphql_validation(self):
        config = {
            ConfigKey.ID: "non-graphql",
            ConfigKey.TYPE: MemberServerType.CLIENT,
            ConfigKey.ENDPOINT: "https://client-endpoint.com"
        }
        validator = ServerConfigValidator(config)
        # Should pass — graphql check is skipped
        validator.validate_graphql_config()
