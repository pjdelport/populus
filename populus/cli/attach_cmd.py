import os
import sys
import textwrap
import hashlib
from datetime import datetime

import click

try:
    from IPython.terminal.embed import InteractiveShellEmbed as InteractiveConsole
    is_ipython = True
except ImportError:
    from code import InteractiveConsole
    is_ipython = False

from eth_rpc_client import Client

import populus
from populus import utils
from populus.contracts import (
    package_contracts,
)
from populus.geth import (
    get_active_data_dir,
    get_known_contracts,
    add_to_known_contracts,
)
from populus.deployment import (
    deploy_contracts,
    validate_deployed_contracts,
)
from populus.cli.deploy_cmd import (
    echo_post_deploy_message
)

from .main import main


def deploy_set(context, client, project_dir, data_dir=None, record=True, contracts_by_name=[]):
    """ Re-Deploy a set of contracts by name or all contracts
        @param context local context for the attach python interpreter.
        @param client RPC client for accessing the ethereum chain
        @param project_dir absolute file path of the project that
            will be interrogated to determine the contracts that
            can be deployed
        @param data_dir directory of the test chain if not None
        @param contracts_by_name if not None, this must be a list
            of strings indicating the names of the contracts to deploy
    """

    if type(contracts_by_name) is not list:
        raise TypeError("Contracts by name must be a list of strings")

    contracts = package_contracts(utils.load_contracts(project_dir))
    deployed_contracts = deploy_contracts(
        deploy_client=client,
        contracts=contracts,
        deploy_at_block=1,
        max_wait_for_deploy=120,
        from_address=None,
        max_wait=120,
        contracts_to_deploy=contracts_by_name,
        dependencies=None,
        constructor_args=None,
        deploy_gas=None,
    )
    validate_deployed_contracts(client, deployed_contracts)
    echo_post_deploy_message(client, deployed_contracts)
    if data_dir is not None and record:
        add_to_known_contracts(deployed_contracts, data_dir)
    # Update the attach shell's context with the latest contracts
    # objects
    context["contracts"] = contracts
    if data_dir is not None:
        setup_known_instances(context, data_dir)
    return(deployed_contracts)


def setup_known_instances(context, data_dir):
    # Attempt to load known contracts.
    knownCts = get_known_contracts(data_dir)
    for name in knownCts.keys():
        addrList = knownCts[name]
        # Latest Instances contains a list of the deployed contracts
        # for which the code matches with the current project
        # context's contract code. We use a sha512 hash to compare
        # the code of each. The idea here is to catch cases where the
        # user has updated their code but failed to redeploy, and
        # cases where new contract methods might attempt to be called
        # on old contract addresses
        latestInstances = []
        ctType = None
        try:
            ctType = getattr(context["contracts"], name)
        except AttributeError:
            click.echo("Failed to find contract `{0}` in project context: skipping".format(name))
            continue
        currCodeHash = hashlib.sha512(ctType._config.code).hexdigest()
        for data in addrList:
            if currCodeHash == data["codehash"]:
                inst = ctType(data["address"], context["client"])
                ts = datetime.strptime(data["ts"], "%Y-%m-%dT%H:%M:%S.%f")
                latestInstances.append((ts, inst))

        # Ok - latestInstances has all the instances of this
        # contract type whose code matches with what we expect
        # it to be. Now let's sort this list by the time
        # stamp
        latestInstances.sort(key=lambda r: r[0])
        setattr(ctType, "known", [x[1] for x in latestInstances])


@main.command()
@click.option(
    '--active/--no-active',
    default=True,
    help=(
        "This flag indicates whether the attach command will use "
        "the chain that is referenced from the <proj>/chains/.active-chain "
        "to load information about known contracts or not."
    ),
)
def attach(active):
    """
    Enter a python shell with contracts and blockchain client
    available.
    """
    project_dir = os.path.abspath(os.getcwd())
    contracts_meta = utils.load_contracts(project_dir)
    client = Client('127.0.0.1', '8545')

    context = {
        'contracts': package_contracts(contracts_meta),
        'client': client,
    }
    data_dir = None
    if active:
        data_dir = get_active_data_dir(project_dir)
        if os.path.islink(data_dir):
            setup_known_instances(context, data_dir)
        else:
            click.echo(click.style("No Valid Active Chain Data Directory Found!", fg="red"))

    def redeploy(contracts=[], record=True):
        return(deploy_set(
            context, client, project_dir, data_dir=data_dir,
            record=record, contracts_by_name=contracts
        ))

    context["redeploy"] = redeploy

    contract_names = ', '.join(sorted(contracts_meta.keys()))

    banner = textwrap.dedent(
        """
        Python: {python_version}

        Populus: v{populus_version}

        Project Path: {project_dir}

        contracts  -> Contract classes
        client     -> Blockchain client ({client_type})
        redeploy   -> Method to reploy project contracts
                      Example:
                        deployed_cts = redeploy()
                        deployed_cts = redeploy(record = False)
                        deployed_cts = redeploy(contracts = ["Example"])

        Contracts: {contracts}
        Check contracts.<type>.known for deployed contracts.

        """
    ).format(
        python_version=sys.version.partition('\n')[0],
        populus_version=populus.__version__,
        project_dir=project_dir,
        client_type="json-rpc",
        contracts=click.wrap_text(
            contract_names, initial_indent='', subsequent_indent=' ' * 4,
        ),
    ).strip()

    if is_ipython:
        shell = InteractiveConsole(user_ns=context)
    else:
        shell = InteractiveConsole(context)
    shell.interact(banner)
