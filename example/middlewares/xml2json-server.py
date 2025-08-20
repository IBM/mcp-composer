from fastmcp import FastMCP
from mcp_composer.middleware.xml2json import FormatXml2Json
import asyncio

app = FastMCP("XML to JSON Demo Server")


# Example tool that returns XML data
@app.tool()
async def get_user_data(user_id: str) -> dict:
    """
    Returns user data in XML format (will be converted to JSON by middleware).
    """
    # Simulate XML response from external service
    xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<user>
    <id>{user_id}</id>
    <name>John Doe</name>
    <email>john.doe@example.com</email>
    <profile>
        <age>30</age>
        <location>New York</location>
        <preferences>
            <theme>dark</theme>
            <language>en</language>
        </preferences>
    </profile>
    <orders>
        <order>
            <id>12345</id>
            <amount>99.99</amount>
            <status>completed</status>
        </order>
        <order>
            <id>12346</id>
            <amount>149.99</amount>
            <status>pending</status>
        </order>
    </orders>
</user>"""

    return {"status": "success", "data": xml_data, "format": "xml"}


@app.tool()
async def get_product_catalog(category: str) -> dict:
    """
    Returns product catalog in XML format.
    """
    xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<catalog category="{category}">
    <product>
        <id>P001</id>
        <name>Laptop</name>
        <price>999.99</price>
        <specifications>
            <cpu>Intel i7</cpu>
            <ram>16GB</ram>
            <storage>512GB SSD</storage>
        </specifications>
    </product>
    <product>
        <id>P002</id>
        <name>Mouse</name>
        <price>29.99</price>
        <specifications>
            <type>Wireless</type>
            <dpi>1200</dpi>
        </specifications>
    </product>
</catalog>"""

    return {"status": "success", "data": xml_data, "format": "xml"}


# Add XML to JSON middleware
app.add_middleware(FormatXml2Json(app))

if __name__ == "__main__":
    app.run()
