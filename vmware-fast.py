#!/usr/bin/env python
import os
import json
import ssl

from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect


def main():
    try:
        username = "administrator@saturn.pok"
        password = "Plecl0udAdm!n"
        host = "9.114.161.31"
    except KeyError as error:
        raise KeyError("Environment variables VMWARE_USERNAME, VMWARE_PASSWORD, and VMWARE_SERVER required") from error
    port = int(os.environ.get("VMWARE_PORT", "443"))
    validate = os.environ.get("VMWARE_VALIDATE_CERTS", "False").lower()

    ssl_context = None
    if validate in ["false", "f", "no", "0"]:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ssl_context.verify_mode = ssl.CERT_NONE

    si = SmartConnect(host=host, user=username, pwd=password, port=port, sslContext=ssl_context)

    ca_group_name_template = "vmware_tag_{key}_{value}"

    # Build a lookup table for custom attributes to go from id to name
    ca_lookup = {}
    for field in si.content.customFieldsManager.field:
        ca_lookup[field.key] = field.name

    inventory = {
        "all": {
            "hosts": []
        },
        "_meta": {
            "hostvars": {}
        }
    }

    # Load all data recursively from the root folder, limiting to only vim.VirtualMachine objects
    container = si.content.rootFolder
    view_type = [vim.VirtualMachine]
    recursive = True
    container_view = si.content.viewManager.CreateContainerView(container, view_type, recursive)
    children = container_view.view

    # For each VM discovered
    for child in children:
        # Templates appear as VirtualMachines to the API, ignore them
        if child.summary.config.template:
            continue

        # Pull the name of the VM
        name = child.summary.config.name

        # Pull IP address
        ip = child.summary.guest.ipAddress

        #set hostvars
        hostvars = {
            "ansible_host": name,
            "ansible_host_ssh": ip,
            "custom_attributes": {}
        }

        # Go through the VM's custom attributes, add them to the hostvars and to the appropriate group
        for value in child.summary.customValue:
            ca_key = ca_lookup[value.key]
            ca_value = value.value
            hostvars["custom_attributes"][ca_key] = ca_value

            # Generate the target group name
            ca_group_name = ca_group_name_template.format(key=ca_key, value=ca_value)
            # Check that the group name exists and create it if it doesn't
            if ca_group_name not in inventory:
                inventory[ca_group_name] = {
                    "hosts": []
                }
            inventory[ca_group_name]["hosts"].append(name)

        inventory["_meta"]["hostvars"][name] = hostvars
        inventory["all"]["hosts"].append(name)

    print(json.dumps(inventory))


if __name__ == "__main__":
    main()