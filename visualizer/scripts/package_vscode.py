"""Build the local VS Code extension without npm downloads or a publishing account."""

import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "visualizer" / "vscode"


def main():
    package = json.loads((SOURCE / "package.json").read_text())
    namespace = "http://schemas.microsoft.com/developer/vsx-schema/2011"
    ET.register_namespace("", namespace)

    def element(parent, name, attributes=None, text=None):
        child = ET.SubElement(parent, f"{{{namespace}}}{name}", attributes or {})
        child.text = text
        return child

    manifest = ET.Element(f"{{{namespace}}}PackageManifest", {"Version": "2.0.0"})
    metadata = element(manifest, "Metadata")
    element(metadata, "Identity", {
        "Id": package["name"], "Version": package["version"],
        "Publisher": package["publisher"], "Language": "en-US",
    })
    element(metadata, "DisplayName", text=package["displayName"])
    element(metadata, "Description", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}, package["description"])
    element(metadata, "Categories", text=",".join(package["categories"]))
    properties = element(metadata, "Properties")
    for key, value in {
        "Microsoft.VisualStudio.Code.Engine": package["engines"]["vscode"],
        "Microsoft.VisualStudio.Code.ExtensionDependencies": ",".join(package["extensionDependencies"]),
        "Microsoft.VisualStudio.Code.ExtensionPack": "",
        "Microsoft.VisualStudio.Code.ExtensionKind": ",".join(package["extensionKind"]),
        "Microsoft.VisualStudio.Code.LocalizedLanguages": "",
        "Microsoft.VisualStudio.Services.GitHubFlavoredMarkdown": "true",
    }.items():
        element(properties, "Property", {"Id": key, "Value": value})
    installation = element(manifest, "Installation")
    element(installation, "InstallationTarget", {"Id": "Microsoft.VisualStudio.Code"})
    element(manifest, "Dependencies")
    assets = element(manifest, "Assets")
    for asset_type, filename in [("Microsoft.VisualStudio.Code.Manifest", "package.json"), ("Microsoft.VisualStudio.Services.Content.Details", "README.md")]:
        element(assets, "Asset", {"Type": asset_type, "Path": f"extension/{filename}", "Addressable": "true"})

    content_types = b'''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json"/>
  <Default Extension="js" ContentType="application/javascript"/>
  <Default Extension="md" ContentType="text/markdown"/>
  <Default Extension="vsixmanifest" ContentType="text/xml"/>
</Types>'''
    destination = ROOT / "dist" / f'{package["name"]}-{package["version"]}.vsix'
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        archive.writestr("extension.vsixmanifest", ET.tostring(manifest, encoding="utf-8", xml_declaration=True))
        archive.writestr("[Content_Types].xml", content_types)
        for filename in ("package.json", "README.md", "extension.js", "bridge.js", "companion.js"):
            archive.write(SOURCE / filename, f"extension/{filename}")
    print(destination)


if __name__ == "__main__":
    main()
