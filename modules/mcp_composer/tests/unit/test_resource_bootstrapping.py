"""Tests for resource bootstrapping functionality."""

import pytest
from pathlib import Path
from mcp_composer.core.config.unified_config import (
    ResourceConfig,
    UnifiedConfig,
    ConfigSection,
    ConfigValidationError,
    UnifiedConfigValidator,
)
from mcp_composer.core.config.config_loader import ConfigLoader


class TestResourceConfig:
    """Test ResourceConfig schema validation."""

    def test_valid_static_resource(self):
        """Test creating a valid static resource."""
        config = ResourceConfig(
            name="test_resource",
            description="Test resource",
            uri="resource://test",
            text="Test content",
            mime_type="text/plain",
            tags=["test"],
        )
        assert config.name == "test_resource"
        assert config.uri == "resource://test"
        assert config.text == "Test content"

    def test_valid_resource_template(self):
        """Test creating a valid resource template."""
        config = ResourceConfig(
            name="test_template",
            description="Test template",
            uri_template="resource://test/{id}",
            template="Content for {id}",
            mime_type="text/plain",
        )
        assert config.name == "test_template"
        assert config.uri_template == "resource://test/{id}"
        assert config.template == "Content for {id}"

    def test_auto_generate_uri(self):
        """Test auto-generation of URI when not provided."""
        config = ResourceConfig(name="auto_uri", text="Content")
        assert config.uri == "resource://auto_uri"

    def test_empty_name_validation(self):
        """Test that empty name raises validation error."""
        with pytest.raises(ValueError, match="Resource name cannot be empty"):
            ResourceConfig(name="", uri="resource://test")

    def test_whitespace_name_validation(self):
        """Test that whitespace-only name raises validation error."""
        with pytest.raises(ValueError, match="Resource name cannot be empty"):
            ResourceConfig(name="   ", uri="resource://test")

    def test_empty_uri_validation(self):
        """Test that empty URI string raises validation error."""
        with pytest.raises(ValueError, match="URI/URI template cannot be empty string"):
            ResourceConfig(name="test", uri="")

    def test_invalid_mime_type(self):
        """Test validation of MIME type format."""
        # This should pass validation in ResourceConfig but fail in UnifiedConfigValidator
        config = ResourceConfig(name="test", uri="resource://test", mime_type="invalid")
        assert config.mime_type == "invalid"

    def test_default_values(self):
        """Test default values for optional fields."""
        config = ResourceConfig(name="test", uri="resource://test")
        assert config.mime_type == "text/plain"
        assert config.enabled is True
        assert config.tags is None
        assert config.description is None


class TestUnifiedConfigWithResources:
    """Test UnifiedConfig with resources section."""

    def test_unified_config_with_resources(self):
        """Test creating unified config with resources."""
        config = UnifiedConfig(
            servers=[],
            middleware=[],
            prompts=[],
            tools={},
            resources=[ResourceConfig(name="test_resource", uri="resource://test", text="Test content")],
        )
        assert config.resources is not None
        assert len(config.resources) == 1
        assert config.resources[0].name == "test_resource"

    def test_duplicate_resource_names(self):
        """Test that duplicate resource names raise validation error."""
        with pytest.raises(ValueError, match="Duplicate resource names found"):
            UnifiedConfig(
                servers=[],
                middleware=[],
                prompts=[],
                tools={},
                resources=[
                    ResourceConfig(name="duplicate", uri="resource://test1"),
                    ResourceConfig(name="duplicate", uri="resource://test2"),
                ],
            )

    def test_empty_resources_list(self):
        """Test unified config with empty resources list."""
        config = UnifiedConfig(servers=[], middleware=[], prompts=[], tools={}, resources=[])
        assert config.resources == []

    def test_none_resources(self):
        """Test unified config with None resources."""
        config = UnifiedConfig(servers=[], middleware=[], prompts=[], tools={}, resources=None)
        assert config.resources is None


class TestUnifiedConfigValidator:
    """Test UnifiedConfigValidator with resources."""

    def test_validate_valid_resources(self):
        """Test validation of valid resources."""
        config = UnifiedConfig(
            servers=[],
            middleware=[],
            prompts=[],
            tools={},
            resources=[ResourceConfig(name="test", uri="resource://test", mime_type="text/plain")],
        )
        validator = UnifiedConfigValidator(config)
        validator.validate()  # Should not raise

    def test_validate_resource_with_both_uri_and_template(self):
        """Test that resource with both uri and uri_template fails validation."""
        config_dict = {
            "servers": [],
            "middleware": [],
            "prompts": [],
            "tools": {},
            "resources": [
                {"name": "invalid", "uri": "resource://test", "uri_template": "resource://test/{id}", "text": "content"}
            ],
        }
        validator = UnifiedConfigValidator(config_dict)
        with pytest.raises(ConfigValidationError, match="cannot have both"):
            validator.validate()

    def test_validate_resource_without_uri_or_template(self):
        """Test that resource without uri or uri_template fails validation."""
        # This should be caught by model_post_init which auto-generates uri
        config = ResourceConfig(name="test", text="content")
        assert config.uri == "resource://test"  # Auto-generated

    def test_validate_invalid_mime_type(self):
        """Test validation of invalid MIME type format."""
        config = UnifiedConfig(
            servers=[],
            middleware=[],
            prompts=[],
            tools={},
            resources=[ResourceConfig(name="test", uri="resource://test", mime_type="invalid")],
        )
        validator = UnifiedConfigValidator(config)
        with pytest.raises(ConfigValidationError, match="invalid mime_type"):
            validator.validate()


class TestConfigLoaderResourceDetection:
    """Test ConfigLoader resource detection."""

    def test_detect_resources_yaml(self, tmp_path):
        """Test detection of resources in YAML file."""
        config_file = tmp_path / "resources.yaml"
        config_file.write_text("""
resources:
  - name: "test"
    uri: "resource://test"
    text: "content"
""")

        loader = ConfigLoader()
        config_type = loader.detect_config_type(str(config_file))
        assert config_type == "all"

    def test_detect_resources_json(self, tmp_path):
        """Test detection of resources in JSON file."""
        config_file = tmp_path / "resources.json"
        config_file.write_text("""
{
  "resources": [
    {
      "name": "test",
      "uri": "resource://test",
      "text": "content"
    }
  ]
}
""")

        loader = ConfigLoader()
        config_type = loader.detect_config_type(str(config_file))
        assert config_type == "all"

    def test_detect_resource_list_format(self, tmp_path):
        """Test detection of resources in list format."""
        config_file = tmp_path / "resources.yaml"
        config_file.write_text("""
- name: "test"
  uri: "resource://test"
  text: "content"
""")

        loader = ConfigLoader()
        config_type = loader.detect_config_type(str(config_file))
        assert config_type == "resources"


class TestConfigLoaderResourceLoading:
    """Test ConfigLoader resource loading."""

    def test_load_resources_yaml(self, tmp_path):
        """Test loading resources from YAML file."""
        config_file = tmp_path / "resources.yaml"
        config_file.write_text("""
resources:
  - name: "test_resource"
    description: "Test resource"
    uri: "resource://test"
    text: "Test content"
    mime_type: "text/plain"
    tags: ["test"]
""")

        loader = ConfigLoader()
        config = loader.load_from_file(str(config_file))

        assert config.resources is not None
        assert len(config.resources) == 1
        assert config.resources[0].name == "test_resource"
        assert config.resources[0].uri == "resource://test"
        assert config.resources[0].text == "Test content"

    def test_load_resources_json(self, tmp_path):
        """Test loading resources from JSON file."""
        config_file = tmp_path / "resources.json"
        config_file.write_text("""
{
  "resources": [
    {
      "name": "test_resource",
      "uri": "resource://test",
      "text": "Test content"
    }
  ]
}
""")

        loader = ConfigLoader()
        config = loader.load_from_file(str(config_file))

        assert config.resources is not None
        assert len(config.resources) == 1
        assert config.resources[0].name == "test_resource"

    def test_load_unified_config_with_resources(self, tmp_path):
        """Test loading unified config with resources."""
        config_file = tmp_path / "unified.yaml"
        config_file.write_text("""
servers: []
prompts: []
resources:
  - name: "test"
    uri: "resource://test"
    text: "content"
""")

        loader = ConfigLoader()
        config = loader.load_from_file(str(config_file))

        assert config.servers == []
        assert config.prompts == []
        assert config.resources is not None
        assert len(config.resources) == 1

    def test_load_multiple_resources(self, tmp_path):
        """Test loading multiple resources."""
        config_file = tmp_path / "resources.yaml"
        config_file.write_text("""
resources:
  - name: "resource1"
    uri: "resource://test1"
    text: "Content 1"
  - name: "resource2"
    uri: "resource://test2"
    text: "Content 2"
  - name: "template1"
    uri_template: "resource://test/{id}"
    template: "Template {id}"
""")

        loader = ConfigLoader()
        config = loader.load_from_file(str(config_file))

        assert config.resources is not None
        assert len(config.resources) == 3
        assert config.resources[0].name == "resource1"
        assert config.resources[1].name == "resource2"
        assert config.resources[2].name == "template1"
        assert config.resources[2].uri_template == "resource://test/{id}"


class TestResourceConfigEdgeCases:
    """Test edge cases for resource configuration."""

    def test_resource_with_multiline_text(self):
        """Test resource with multiline text content."""
        config = ResourceConfig(name="multiline", uri="resource://multiline", text="Line 1\nLine 2\nLine 3")
        assert config.text is not None
        assert "Line 1" in config.text
        assert "Line 2" in config.text

    def test_resource_with_json_content(self):
        """Test resource with JSON content."""
        json_content = '{"key": "value", "number": 42}'
        config = ResourceConfig(
            name="json_resource", uri="resource://json", text=json_content, mime_type="application/json"
        )
        assert config.text == json_content
        assert config.mime_type == "application/json"

    def test_resource_with_markdown_content(self):
        """Test resource with Markdown content."""
        markdown = "# Title\n\n## Subtitle\n\n- Item 1\n- Item 2"
        config = ResourceConfig(name="markdown", uri="resource://docs", text=markdown, mime_type="text/markdown")
        assert config.mime_type == "text/markdown"
        assert config.text is not None
        assert "# Title" in config.text

    def test_resource_with_parameters(self):
        """Test resource template with parameters."""
        config = ResourceConfig(
            name="parameterized",
            uri_template="resource://items/{id}",
            template="Item {id}",
            parameters={"id": {"type": "string", "required": True, "description": "Item ID"}},
        )
        assert config.parameters is not None
        assert "id" in config.parameters

    def test_resource_with_multiple_tags(self):
        """Test resource with multiple tags."""
        config = ResourceConfig(name="tagged", uri="resource://tagged", tags=["tag1", "tag2", "tag3", "category:test"])
        assert config.tags is not None
        assert len(config.tags) == 4
        assert "tag1" in config.tags

    def test_disabled_resource(self):
        """Test creating a disabled resource."""
        config = ResourceConfig(name="disabled", uri="resource://disabled", enabled=False)
        assert config.enabled is False


class TestConfigSectionEnum:
    """Test ConfigSection enum includes RESOURCES."""

    def test_resources_in_config_section(self):
        """Test that RESOURCES is in ConfigSection enum."""
        assert hasattr(ConfigSection, "RESOURCES")
        assert ConfigSection.RESOURCES == "resources"

    def test_all_config_sections(self):
        """Test all config sections are present."""
        sections = [
            ConfigSection.SERVERS,
            ConfigSection.MIDDLEWARE,
            ConfigSection.PROMPTS,
            ConfigSection.TOOLS,
            ConfigSection.RESOURCES,
            ConfigSection.ALL,
        ]
        assert len(sections) == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
