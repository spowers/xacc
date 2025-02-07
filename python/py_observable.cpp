/*******************************************************************************
 * Copyright (c) 2019 UT-Battelle, LLC.
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the Eclipse Public License v1.0
 * and Eclipse Distribution License v1.0 which accompanies this
 * distribution. The Eclipse Public License is available at
 * http://www.eclipse.org/legal/epl-v10.html and the Eclipse Distribution
 *License is available at https://eclipse.org/org/documents/edl-v10.php
 *
 * Contributors:
 *   Alexander J. McCaskey - initial API and implementation
 *******************************************************************************/
#include "py_observable.hpp"
#include "PauliOperator.hpp"
#include "FermionOperator.hpp"
#include "xacc_service.hpp"
#include "py_heterogeneous_map.hpp"

using namespace xacc::quantum;

void bind_observable(py::module &m) {

  py::class_<xacc::Observable, std::shared_ptr<xacc::Observable>, PyObservable>(
      m, "Observable", "The Observable interface.")
      .def(py::init<>(), "")
      .def("observe",
           (std::vector<std::shared_ptr<xacc::CompositeInstruction>>(
               xacc::Observable::*)(
               std::shared_ptr<xacc::CompositeInstruction>)) &
               xacc::Observable::observe,
           "")
      .def("toString", &xacc::Observable::toString,
           "Return string representation of this Observable.")
      .def("nBits", &xacc::Observable::nBits,
           "Return the number of bits this Observable represents.")
      .def("fromOptions",
           (void (xacc::Observable::*)(const HeterogeneousMap &)) &
               xacc::Observable::fromOptions,
           "")
      .def("fromString",
           (void (xacc::Observable::*)(const std::string)) &
               xacc::Observable::fromString,
           "");

  py::class_<Term>(m, "Term").def("coeff", &Term::coeff).def("ops", &Term::ops);
  py::class_<PauliOperator, xacc::Observable, std::shared_ptr<PauliOperator>>(
      m, "PauliOperator")
      .def(py::init<>())
      .def(py::init<std::complex<double>>())
      .def(py::init<double>())
      .def(py::init<std::string>())
      .def(py::init<std::map<int, std::string>>())
      .def(py::init<std::map<int, std::string>, double>())
      .def(py::init<std::map<int, std::string>, std::complex<double>>())
      .def(py::init<std::map<int, std::string>, std::string>())
      .def(py::init<std::map<int, std::string>, std::complex<double>,
                    std::string>())
      .def(py::self + py::self)
      .def(py::self += py::self)
      .def(py::self *= py::self)
      .def(py::self *= double())
      .def(py::self * py::self)
      .def(py::self *= std::complex<double>())
      .def(py::self -= py::self)
      .def(py::self - py::self)
      .def("__eq__", &PauliOperator::operator==)
      .def("__repr__", &PauliOperator::toString)
      .def("eval", &PauliOperator::eval)
      .def("toBinaryVectors", &PauliOperator::toBinaryVectors)
      .def("toXACCIR", &PauliOperator::toXACCIR)
      .def("fromXACCIR", &PauliOperator::fromXACCIR)
      .def("fromString", &PauliOperator::fromString)
      .def("nTerms", &PauliOperator::nTerms)
      .def("isClose", &PauliOperator::isClose)
      .def("commutes", &PauliOperator::commutes)
      .def("__len__", &PauliOperator::nTerms)
      .def("nQubits", &PauliOperator::nQubits)
      .def("computeActionOnKet", &PauliOperator::computeActionOnKet)
      .def("computeActionOnBra", &PauliOperator::computeActionOnBra)
      .def(
          "__iter__",
          [](PauliOperator &op) {
            return py::make_iterator(op.begin(), op.end());
          },
          py::keep_alive<0, 1>());
  m.def("getObservable",
        [](const std::string &type,
           const std::string representation) -> std::shared_ptr<Observable> {
          if (type == "pauli") {
            return representation.empty()
                       ? std::make_shared<PauliOperator>()
                       : std::make_shared<PauliOperator>(representation);
          } else if (type == "fermion") {
            return representation.empty()
                       ? std::make_shared<FermionOperator>()
                       : std::make_shared<FermionOperator>(representation);
          } else if (xacc::hasService<Observable>(type)) {
            auto obs = xacc::getService<Observable>(type);
            obs->fromString(representation);
            return obs;
          } else {
            xacc::error("Invalid observable type");
            return std::make_shared<PauliOperator>();
          }
        });

  m.def("getObservable",
        [](const std::string &type,
           const PyHeterogeneousMap &options) -> std::shared_ptr<Observable> {
          std::shared_ptr<Observable> t;
          if (xacc::hasService<Observable>(type)) {
            t = xacc::getService<Observable>(type, false);
          } else if (xacc::hasContributedService<Observable>(type)) {
            t = xacc::getContributedService<Observable>(type, false);
          }

          if (!t) {
              xacc::error("Invalid Observable type name " + type + ", can't find in service registry.");
          }
          HeterogeneousMap m;
          for (auto &item : options) {
            PyHeterogeneousMap2HeterogeneousMap vis(m, item.first);
            mpark::visit(vis, item.second);
          }
          t->fromOptions(m);
          return t;
        });
        
      m.def("getObservable",
        [](const std::string &type) -> std::shared_ptr<Observable> {
          std::shared_ptr<Observable> t;
          if (xacc::hasService<Observable>(type)) {
            t = xacc::getService<Observable>(type, false);
          } else if (xacc::hasContributedService<Observable>(type)) {
            t = xacc::getContributedService<Observable>(type, false);
          }

          if (!t) {
              xacc::error("Invalid Observable type name " + type + ", can't find in service registry.");
          }
          HeterogeneousMap m;
          t->fromOptions(m);
          return t;
        });
}