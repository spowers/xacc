import xacc
from pelix.ipopo.decorators import ComponentFactory, Property, Requires, Provides, \
    Validate, Invalidate, Instantiate

@ComponentFactory("aer_accelerator_factory")
@Provides("accelerator")
@Property("_accelerator", "accelerator", "aer")
@Property("_name", "name", "aer")
@Instantiate("aer_accelerator_instance")
class AerAccelerator(xacc.Accelerator):
    def __init__(self):
        xacc.Accelerator.__init__(self)
        self.shots = 1024
        self.backend = None
        self.noise_model = None
        self.modeled_qpu = None

    def getProperties(self):
        if self.backend is not None:
            return self.modeled_qpu.getProperties()

    def initialize(self, options):
        self.qobj_compiler = xacc.getCompiler('qobj')
        if 'shots' in options:
            self.shots = options['shots']

        if 'backend' in options:
            self.backend = options['backend']
            import json
            from qiskit.providers.models.backendproperties import BackendProperties
            from qiskit.providers.aer import noise
            self.modeled_qpu = xacc.getAccelerator('ibm:'+self.backend)
            props = self.modeled_qpu.getProperties()
            jsonStr = props['total-json']
            properties = BackendProperties.from_dict(json.loads(jsonStr))
            ro_error = True if 'readout_error' in options and options['readout_error'] else False
            rel = True if 'thermal_relaxation' in options and options['thermal_relaxation'] else False
            ge = True if 'gate_error' in options and options['gate_error'] else False
            self.noise_model = noise.device.basic_device_noise_model(properties, readout_error=ro_error, thermal_relaxation=rel, gate_error=ge)

    def name(self):
        return 'aer'

    def execute_one_qasm(self, buffer, program):
        qobjStr = self.qobj_compiler.translate(program)
        import json
        from qiskit import Aer
        from qiskit.qobj import (QasmQobj, QobjHeader,
                         QasmQobjInstruction,
                         QasmQobjExperiment, QasmQobjExperimentConfig, QobjExperimentHeader, QasmQobjConfig)
        qobj_json = json.loads(qobjStr)

        # Create the Experiments using qiskit data structures
        exps = [QasmQobjExperiment(config=QasmQobjExperimentConfig(memory_slots=e['config']['memory_slots'], n_qubits=e['config']['n_qubits']),
                    header=QobjExperimentHeader(clbit_labels=e['header']['clbit_labels'],creg_sizes=e['header']['creg_sizes'],
                                                memory_slots=e['header']['memory_slots'],n_qubits=e['header']['n_qubits'],
                                                name=e['header']['name'], qreg_sizes=e['header']['qreg_sizes'],
                                                qubit_labels=e['header']['qubit_labels']),
                    instructions=[QasmQobjInstruction(name=i['name'], qubits=i['qubits'], params=(i['params'] if 'params' in i else [])) if i['name'] != 'measure'
                                    else QasmQobjInstruction(name=i['name'], qubits=i['qubits'], memory=i['memory']) for i in e['instructions']]) for e in qobj_json['qObject']['experiments']]

        qobj = QasmQobj(qobj_id=qobj_json['qObject']['qobj_id'],
                        header=QobjHeader(), config=QasmQobjConfig(shots=self.shots, memory_slots=qobj_json['qObject']['config']['memory_slots']), experiments=exps, shots=self.shots)

        measures = {}
        for i in exps[0].instructions:
            if i.name == "measure":
                measures[i.memory[0]] =i.qubits[0]

        backend = Aer.get_backend('qasm_simulator')

        if self.noise_model is not None:
            job_sim = backend.run(qobj, noise_model=self.noise_model)
        else:
            job_sim = backend.run(qobj)

        sim_result = job_sim.result()


        for b,c in sim_result.get_counts().items():
            bitstring = b
            if len(b) < buffer.size():
                tmp = ['0' for i in range(buffer.size())]
                for bit_loc, qubit in measures.items():
                    tmp[len(tmp)-1-qubit] = list(b)[bit_loc]
                bitstring = ''.join(tmp)
            buffer.appendMeasurement(bitstring,c)

    def execute(self, buffer, programs):

        # Translate IR to a Qobj Json String
        if isinstance(programs, list) and len(programs) > 1:
            for p in programs:
                tmpBuffer = xacc.qalloc(buffer.size())
                tmpBuffer.setName(p.name())
                self.execute_one_qasm(tmpBuffer, p)
                buffer.appendChild(p.name(),tmpBuffer)
        else:
            if isinstance(programs, list):
                programs = programs[0]
            self.execute_one_qasm(buffer, programs)

