#!/usr/bin/env python3
"""
Copyright (c) 2023 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

__author__ = "Trevor Maco <tmaco@cisco.com>"
__copyright__ = "Copyright (c) 2023 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

import csv
import sys

import meraki
from meraki import APIError
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

import config

# Rich Console Instance
console = Console()

# Create a Meraki API client
dashboard = meraki.DashboardAPI(config.API_KEY, suppress_logging=True)


def get_org_id(org_name):
    """
    Get Org Id from Org Name
    :param org_name: Org name
    :return: Org ID
    """
    orgs = dashboard.organizations.getOrganizations()
    org_id = None
    for org in orgs:
        if org['name'] == org_name:
            org_id = org['id']

    if not org_id:
        console.print(f"[red]Error: Org. Name {config.ORG_NAME} not found...[/]")
        sys.exit(-1)
    else:
        return org_id


def create_exclusions(csv_file_name):
    """
    Create VPN Exclusions (in Meraki format), using rules defined in CSV File
    :param csv_file_name: CSV with exclusion rule content
    :return: list of exclusions (in Meraki API format)
    """
    # Read data from the CSV file
    with open(csv_file_name, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)

        custom_exclusions = []
        for row in csv_reader:
            # Extract data from the CSV row
            destination = row['destination'].strip().lower()
            port = row['port'].strip().lower()
            protocol = row['protocol'].strip().lower()

            # Append to exclusion rules (translate to Meraki format)
            custom_exclusions.append({
                'protocol': protocol,
                'port': port,
                'destination': destination
            })

    return custom_exclusions


def add_exclusions_to_network(networks, custom_exclusions, existing_rules):
    """
    Add VPN exclusions to each network in organization
    :param existing_rules: existing_rules (custom) for each network
    :param networks: Organization networks
    :param custom_exclusions: VPN exclusions (Meraki format)
    """
    with Progress() as progress:
        overall_progress = progress.add_task("Overall Progress", total=len(networks), transient=True)
        counter = 1
        new_exclusion_count = len(custom_exclusions)

        for network in networks:
            progress.console.print(
                "Processing Network: [blue]{}[/] ({} of {})".format(network['name'], str(counter), len(networks)))

            try:
                # Define new vpn exclusions and major app's we are going to add to the network
                new_exclusions = custom_exclusions
                new_majorApplications = []

                # Grab existing Rules (if present, no networks will be present if overwrite set to True)
                if network['id'] in existing_rules:
                    new_exclusions += existing_rules[network['id']]['custom']
                    new_majorApplications += existing_rules[network['id']]['majorApplications']

                # Add VPN exclusions to network
                response = dashboard.appliance.updateNetworkApplianceTrafficShapingVpnExclusions(network['id'],
                                                                                                 custom=new_exclusions,
                                                                                                 majorApplications=new_majorApplications
                                                                                                 )
                progress.console.print(f"[green]Successfully added {new_exclusion_count} new exclusion rules![/]")
            except APIError as e:
                progress.console.print(f'[red]Error: {str(e)}[/]')

            counter += 1
            progress.update(overall_progress, advance=1)


def main():
    console.print(Panel.fit("Meraki VPN Exclusion Tool"))

    # Find org id
    console.print(Panel.fit("Get Org ID", title="Step 1"))
    org_id = get_org_id(config.ORG_NAME)

    console.print(f"Found {org_id} for [green]{config.ORG_NAME}![/]")

    # Get appliance networks in org
    console.print(Panel.fit("Get Appliance Networks", title="Step 2"))
    networks = dashboard.organizations.getOrganizationNetworks(organizationId=org_id, total_pages='all')
    networks = [network for network in networks if 'appliance' in network['productTypes']]

    console.print(f"Found {len(networks)} Appliance Networks")

    # Get Existing Rules (Prevent Overwrite if Parameter Set)
    existing_rules = {}
    if not config.OVERWRITE:
        console.print(Panel.fit("Gathering Existing VPN Custom Exclusions", title="Step 2a"))
        response = dashboard.appliance.getOrganizationApplianceTrafficShapingVpnExclusionsByNetwork(org_id, total_pages='all')

        for network_rules in response['items']:
            existing_rules[network_rules['networkId']] = {'custom': network_rules['custom'], 'majorApplications': network_rules['majorApplications']}

        console.print(f'Existing exclusions found: {existing_rules}')

    # Read data from CSV, create exclusion rule payloads in the proper format
    console.print(Panel.fit("Creating VPN Custom Exclusions", title="Step 3"))
    custom_exclusions = create_exclusions(config.CSV_FILE)

    console.print(f'Custom exclusions created: {custom_exclusions}')

    # Add custom exclusions to each network
    console.print(Panel.fit("Adding VPN Custom Exclusions to Networks", title="Step 4"))
    add_exclusions_to_network(networks, custom_exclusions, existing_rules)


if __name__ == "__main__":
    main()
