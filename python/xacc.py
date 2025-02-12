# *******************************************************************************
# Copyright (c) 2019 UT-Battelle, LLC.
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v1.0
# and Eclipse Distribution License v.10 which accompany this distribution.
# The Eclipse Public License is available at http://www.eclipse.org/legal/epl-v10.html
# and the Eclipse Distribution License is available at
# https://eclipse.org/org/documents/edl-v10.php
#
# Contributors:
#   Alexander J. McCaskey - initial API and implementation
# *******************************************************************************/
import atexit
from _pyxacc import *
import os
import time
import json
import platform
import sys
import re
import sysconfig
import argparse
import inspect
import subprocess
import pelix.framework
from pelix.utilities import use_service
from abc import abstractmethod, ABC
import configparser
from pelix.ipopo.constants import use_ipopo
hasPluginGenerator = False
try:
    from plugin_generator import plugin_generator
    hasPluginGenerator = True
except:
    pass


class BenchmarkAlgorithm(ABC):

    # Override this execute method to implement the algorithm
    # @input inputParams
    # @return buffer
    @abstractmethod
    def execute(self, inputParams):
        pass

    # Override this analyze method called to manipulate result data from executing the algorithm
    # @input buffer
    # @input inputParams
    @abstractmethod
    def analyze(self, buffer, inputParams):
        pass


def parse_args(args):
    parser = argparse.ArgumentParser(description="XACC Framework Utility.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     fromfile_prefix_chars='@')
    parser.add_argument("-c", "--set-credentials", type=str,
                        help="Set your credentials for any of the remote Accelerators.", required=False)
    parser.add_argument("-k", "--api-key", type=str,
                        help="The API key for the remote Accelerators.", required=False)
    parser.add_argument("-u", "--user-id", type=str,
                        help="The User Id for the remote Accelerators.", required=False)
    parser.add_argument(
        "--url", type=str, help="The URL for the remote Accelerators.", required=False)
    parser.add_argument("-g", "--group", type=str,
                        help="The IBM Q Group.", required=False)
    parser.add_argument("--hub", type=str, help="The IBM Q Hub.",
                        default='ibm-q-ornl', required=False)
    parser.add_argument("-p", "--project", type=str,
                        help="The IBM Q Project.", required=False)
    parser.add_argument("-L", "--location", action='store_true',
                        help="Print the path to the XACC install location.", required=False)
    parser.add_argument("--python-include-dir", action='store_true',
                        help="Print the path to the Python.h.", required=False)
    parser.add_argument("--benchmark", type=str,
                        help="Run the benchmark detailed in the given input file.", required=False)
    parser.add_argument("--benchmark-requires", type=str,
                        help="List the required services of specified BenchmarkAlgorithm.", required=False)
    parser.add_argument("--benchmark-service", type=str,
                        help="List the plugin names and files of specified service.", required=False)
    parser.add_argument("--benchmark-install", type=str,
                        help="Pull and install the benchmark specified plugin package.", required=False)
    # parser.add_argument("--list-backends", type=str, help="List the backends available for the provided Accelerator.", required=False)

    if hasPluginGenerator:
        subparsers = parser.add_subparsers(title="subcommands", dest="subcommand",
                                           description="Run python3 -m xacc [subcommand] -h for more information about a specific subcommand")
        plugin_generator.add_subparser(subparsers)

        opts = parser.parse_args(args)

    if opts.set_credentials and not opts.api_key:
        print('Error in arg input, must supply api-key if setting credentials')
        sys.exit(1)

    return opts


def initialize():
    xaccHome = os.environ['HOME']+'/.xacc'
    if not os.path.exists(xaccHome):
        os.makedirs(xaccHome)

    try:
        file = open(xaccHome+'/.internal_plugins', 'r')
        contents = file.read()
    except IOError:
        file = open(xaccHome+'/.internal_plugins', 'w')
        contents = ''

    file.close()

    file = open(xaccHome+'/.internal_plugins', 'w')

    xaccLocation = os.path.dirname(os.path.realpath(__file__))
    if platform.system() == "Darwin":
        libname1 = "libxacc-quantum-gate.dylib"
        libname2 = "libxacc-quantum-annealing.dylib"
    else:
        libname1 = "libxacc-quantum-gate.so"
        libname2 = "libxacc-quantum-annealing.so"

    if xaccLocation+'/lib/'+libname1+'\n' not in contents:
        file.write(xaccLocation+'/lib/'+libname1+'\n')
    if xaccLocation+'/lib/'+libname2+'\n' not in contents:
        file.write(xaccLocation+'/lib/'+libname2+'\n')

    file.write(contents)
    file.close()
    setIsPyApi()
    PyInitialize(xaccLocation)

def setCredentials(opts):
    defaultUrls = {'ibm': 'https://quantumexperience.ng.bluemix.net',
                   'rigetti': 'https://api.rigetti.com/qvm', 'dwave': 'https://cloud.dwavesys.com'}
    acc = opts.set_credentials
    url = opts.url if not opts.url == None else defaultUrls[acc]
    if acc == 'rigetti' and not os.path.exists(os.environ['HOME']+'/.pyquil_config'):
        apikey = opts.api_key
        if opts.user_id == None:
            print('Error, must provide user-id for Rigetti accelerator')
            sys.exit(1)
        user = opts.user_id
        f = open(os.environ['HOME']+'/.pyquil_config', 'w')
        f.write('[Rigetti Forest]\n')
        f.write('key: ' + apikey + '\n')
        f.write('user_id: ' + user + '\n')
        f.write('url: ' + url + '\n')
        f.close()
    elif acc == 'ibm' and (opts.group != None or opts.project != None):
        # We have hub,group,project info coming in.
        if (opts.group != None and opts.project == None) or (opts.group == None and opts.project != None):
            print('Error, you must provide both group and project')
            sys.exit(1)
        f = open(os.environ['HOME']+'/.'+acc+'_config', 'w')
        f.write('key: ' + opts.api_key + '\n')
        f.write('url: ' + url + '\n')
        f.write('hub: ' + opts.hub + '\n')
        f.write('group: ' + opts.group + '\n')
        f.write('project: ' + opts.project + '\n')
        f.close()
    else:
        if not os.path.exists(os.environ['HOME']+'/.'+acc+'_config'):
            f = open(os.environ['HOME']+'/.'+acc+'_config', 'w')
            f.write('key: ' + opts.api_key + '\n')
            f.write('url: ' + url + '\n')
            f.close()
    fname = acc if 'rigetti' not in acc else 'pyquil'
    print('\nCreated '+acc+' config file:\n$ cat ~/.'+fname+'_config:')
    print(open(os.environ['HOME']+'/.'+fname+'_config', 'r').read())

class DecoratorFunction(ABC):

    def __init__(self):
        pass

    def initialize(self, f, *args, **kwargs):
        self.function = f
        self.args = args
        self.kwargs = kwargs
        self.__dict__.update(kwargs)
        self.qpu = None
        self.src = '\n'.join(inspect.getsource(self.function).split('\n')[1:])

        self.processVariables()

        compiler = getCompiler('pyxasm')
        if self.accelerator == None:
            if 'accelerator' in self.kwargs:
                if isinstance(self.kwargs['accelerator'], Accelerator):
                    self.qpu = self.kwargs['accelerator']
                else:
                    self.qpu = getAccelerator(self.kwargs['accelerator'])
            elif hasAccelerator('tnqvm'):
                self.qpu = getAccelerator('tnqvm')
            else:
                print(
                    '\033[1;31mError, no Accelerators installed. We suggest installing TNQVM.\033[0;0m')
                exit(0)
        else:
            self.qpu = self.accelerator

        ir = compiler.compile(self.src, self.qpu)
        self.compiledKernel = ir.getComposites()[0]

    def overrideAccelerator(self, acc):
        self.qpu = acc

    def processVariables(self):
        g = re.findall('=(\w+)', self.src)
        frame = inspect.currentframe()
        for thing in g:
            if thing in frame.f_back.f_locals['f'].__globals__:
                if isinstance(frame.f_back.f_locals['f'].__globals__[thing], str):
                    real = "'" + \
                        frame.f_back.f_locals['f'].__globals__[thing] + "'"
                else:
                    real = str(frame.f_back.f_locals['f'].__globals__[thing])
                self.src = self.src.replace('='+thing, '='+real)
        del frame

    def nParameters(self):
        return self.getFunction().nParameters()

    def getCompositeInstruction(self):
        return self.compiledKernel

    def modifyAlgorithm(self, algorithm):
        newAlgo = serviceRegistry.get_service(
            'decorator_algorithm_service', algorithm)
        self.__class__ = newAlgo.__class__

    @abstractmethod
    def __call__(self, *args, **kwargs):
        pass


class WrappedF(DecoratorFunction):

    def __init__(self, f, *args, **kwargs):
        self.function = f
        self.args = args
        self.kwargs = kwargs
        self.__dict__.update(kwargs)
        self.accelerator = None

    def __call__(self, *args, **kwargs):
        super().__call__(*args, **kwargs)
        argsList = list(args)
        if not isinstance(argsList[0], AcceleratorBuffer):
            raise RuntimeError(
                'First argument of an xacc kernel must be the Accelerator Buffer to operate on.')
        fevaled = self.compiledKernel.eval(argsList[1:])
        self.qpu.execute(argsList[0], fevaled)
        return


class qpu(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.__dict__.update(kwargs)
        return

    def __call__(self, f):
        if 'algo' in self.kwargs:
            servName = self.kwargs['algo']
            function = serviceRegistry.get_service(
                'decorator_algorithm_service', servName)
            function.initialize(f, *self.args, **self.kwargs)
            return function
        else:
            wf = WrappedF(f, *self.args, **self.kwargs)
            wf.initialize(f, *self.args, **self.kwargs)
            return wf

'''The following code provides the hooks necessary for executing benchmarks with XACC'''


class PyServiceRegistry(object):
    def __init__(self):
        self.framework = pelix.framework.create_framework((
            "pelix.ipopo.core",
            "pelix.shell.console"))
        self.framework.start()
        self.context = self.framework.get_bundle_context()
        self.registry = {}

    def initialize(self):
        serviceList = ['decorator_algorithm_service', 'benchmark_algorithm',
                       'hamiltonian_generator', 'ansatz_generator', 'accelerator',
                       'irtransformation', 'observable', 'optimizer']
        xaccLocation = os.path.dirname(os.path.realpath(__file__))
        self.pluginDir = xaccLocation + '/py-plugins'
        if not os.path.exists(self.pluginDir):
            os.makedirs(self.pluginDir)
        sys.path.append(self.pluginDir)

        pluginFiles = [f for f in os.listdir(
            self.pluginDir) if os.path.isfile(os.path.join(self.pluginDir, f))]
        for f in pluginFiles:
            bundle_name = os.path.splitext(f)[0].strip()
            self.context.install_bundle(bundle_name).start()
        for servType in serviceList:
            self.get_algorithm_services(servType)

        for accName, acc in self.registry['accelerator'].items():
            contributeService(accName, acc)
        for irtName, irt in self.registry['irtransformation'].items():
            contributeService(irtName, irt)
        for obsName, obs in self.registry['observable'].items():
            contributeService(obsName, obs)
        for optName, opt in self.registry['optimizer'].items():
            contributeService(optName, opt)

    def get_algorithm_services(self, serviceType):
        tmp = self.context.get_all_service_references(serviceType)
        if tmp is not None:
            for component in tmp:
                name = component.get_properties()['name']
                if serviceType not in self.registry:
                    self.registry[serviceType] = {
                        name: self.context.get_service(component)}
                else:
                    self.registry[serviceType].update(
                        {name: self.context.get_service(component)})
            return tmp

    def get_service(self, serviceName, name):
        service = None
        try:
            available_services = self.registry[serviceName]
            service = available_services[name]
        except KeyError:
            info("""There is no '{0}' with the name '{1}' available.
    1. Install the '{1}' '{0}' to the Python plugin directory.
    2. Make sure all required services for '{1}' are installed.\n""".format(serviceName, name, ""))
            if serviceName == "benchmark_algorithm":
                self.get_benchmark_requirements(name)
            exit(1)
        return service

    def get_benchmark_requirements(self, name):
        with use_ipopo(self.context) as ipopo:
            requirements = []
            try:
                details = ipopo.get_instance_details(
                    name+"_benchmark")['dependencies']
            except ValueError as ex:
                info(
                    "There is no benchmark_algorithm service with the name '{}' available.".format(name))
                exit(1)
            for k, v in details.items():
                requirements.append(v['specification'])
            if not requirements:
                info(
                    "There are no required services for '{}' BenchmarkAlgorithm.".format(name))
                exit(1)
            info("Required benchmark services for '{}' BenchmarkAlgorithm:".format(name))
            for i, r in enumerate(requirements):
                info("{}. {}".format(i+1, r))

    def get_component_names(self, serviceType):
        tmp = self.context.get_all_service_references(serviceType)
        names_and_files = {}
        try:
            for component in tmp:
                b = component.get_bundle()
                names_and_files[component.get_properties(
                )['name']] = b.get_symbolic_name()
        except TypeError as ex:
            info("There are no plugins with service reference '{}' available.".format(
                serviceType))
            exit(1)
        info("Names and files of plugins that provide service reference '{}':".format(
            serviceType))
        for i, (k, v) in enumerate(names_and_files.items()):
            info("{}. {}  --> {}.py".format(i+1, k, v))

    def install_plugins(self, pkg):
        dest = os.path.dirname(os.path.realpath(__file__))+"/benchmark"
        os.chdir(dest)
        if "list" in pkg:
            subprocess.run([sys.executable, 'manage.py', "-l"])
        else:
            subprocess.run([sys.executable, 'manage.py', '-p',
                            "{}".format(self.pluginDir), '-i', "{}".format(pkg)])


if not pelix.framework.FrameworkFactory.is_framework_running(None):
    serviceRegistry = PyServiceRegistry()
    serviceRegistry.initialize()


def benchmark(opts):
    if opts.benchmark is not None:
        inputfile = opts.benchmark
        xacc_settings = process_benchmark_input(inputfile)
    else:
        error('Must provide input file for benchmark.')
        return

    Initialize()

    if ':' in xacc_settings['accelerator']:
        accelerator, backend = xacc_settings['accelerator'].split(':')
        setOption(accelerator + "-backend", backend)
        xacc_settings['accelerator'] = accelerator

    accelerator = xacc_settings['accelerator']
    if 'n-shots' in xacc_settings:
        if 'local-ibm' in accelerator:
            accelerator = 'ibm'
        setOption(accelerator+('-trials' if 'rigetti' in accelerator else '-shots'),
                  xacc_settings['n-shots'])
    # Using ServiceRegistry to getService (benchmark_algorithm_service) and execute the service
    algorithm = serviceRegistry.get_service(
        'benchmark_algorithm', xacc_settings['algorithm'])
    if algorithm is None:
        print("XACC algorithm service with name " +
              xacc_settings['algorithm'] + " is not installed.")
        exit(1)

    starttime = time.time()
    buffer = algorithm.execute(xacc_settings)
    elapsedtime = time.time() - starttime
    buffer.addExtraInfo("benchmark-time", elapsedtime)
    for k, v in xacc_settings.items():
        buffer.addExtraInfo(k, v)
    # Analyze the buffer
    head, tail = os.path.split(inputfile)
    buffer.addExtraInfo('file-name', tail)
    algorithm.analyze(buffer, xacc_settings)
    timestr = time.strftime("%Y%m%d-%H%M%S")
    results_name = "%s_%s_%s_%s" % (os.path.splitext(
        tail)[0], xacc_settings['accelerator'], xacc_settings['algorithm'], timestr)
    f = open(results_name+".ab", 'w')
    f.write(str(buffer))
    f.close()

    Finalize()


def process_benchmark_input(filename):
    config = configparser.RawConfigParser()
    try:
        with open(filename) as f:
            framework_settings = {}
            config.read(filename)
            for section in config.sections():
                temp = dict(config.items(section))
                framework_settings.update(temp)
            return framework_settings
    except:
        print("Input file " + filename + " could not be opened.")
        exit(1)


def main(argv=None):
    opts = parse_args(sys.argv[1:])
    xaccLocation = os.path.dirname(os.path.realpath(__file__))

    if opts.location:
        print(xaccLocation)
        sys.exit(0)

    if hasPluginGenerator and opts.subcommand == "generate-plugin":
        plugin_generator.run_generator(opts, xaccLocation)
        sys.exit(0)

    if opts.python_include_dir:
        print(sysconfig.get_paths()['platinclude'])
        sys.exit(0)

    # if opts.framework_help:
    #     Initialize(['--help'])
    #     return

    # if opts.list_backends is not None:
    #     acc = opts.list_backends
    #     if acc == 'ibm':
    #         info('Retrieving remote IBM backend information')
    #         Initialize(['--'+acc+'-list-backends'])
    #     elif acc == 'dwave':
    #         info('Retrieving remote D-Wave solver information')
    #         Initialize(['--'+acc+'-list-solvers'])
    #     return

    if not opts.set_credentials == None:
        setCredentials(opts)

    if not opts.benchmark == None:
        benchmark(opts)

    if not opts.benchmark_requires == None:
        serviceRegistry.get_benchmark_requirements(opts.benchmark_requires)

    if not opts.benchmark_service == None:
        serviceRegistry.get_component_names(opts.benchmark_service)

    if not opts.benchmark_install == None:
        serviceRegistry.install_plugins(opts.benchmark_install)


initialize()


def _finalize():
    Finalize()


atexit.register(_finalize)

if __name__ == "__main__":
    sys.exit(main())
