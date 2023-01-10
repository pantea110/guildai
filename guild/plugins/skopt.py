# Copyright 2017-2022 RStudio, PBC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import yaml

import guild

from guild import flag_util
from guild import model as modellib
from guild import model_proxy
from guild import plugin as pluginlib


class SkoptModelProxy:
    def __init__(self):
        self.name = "skopt"
        self.reference = modellib.ModelRef(
            "builtin",
            "guildai",
            guild.__version__,
            self.name,
        )
        self.modeldef = model_proxy.modeldef(
            self.name,
            {
                "operations": _skopt_opdefs(),
            },
            f"<{self.__class__.__name__}>",
        )


def _skopt_opdefs():
    opdefs = yaml.safe_load(
        """
    random:
      description:
        Batch processor supporting random flag value generation.
      exec: ${python_exe} -um guild.plugins.random_main
      delete-on-success: yes
      can-stage-trials: yes

    gp:
      description:
        Bayesian optimizer using Gaussian processes.

        Refer to https://scikit-optimize.github.io/#skopt.gp_minimize
        for details on this algorithm and its flags.
      exec: ${python_exe} -um guild.plugins.skopt_gp_main
      flags:
        random-starts:
          description:
            Number of trials using random values before optimizing
          default: 3
          type: int
        acq-func:
          description:
            Function to minimize over the gaussian prior
          default: gp_hedge
          choices:
            - value: LCB
              description: Lower confidence bound
            - value: EI
              description: Negative expected improvement
            - value: PI
              description: Negative probability of improvement
            - value: gp_hedge

              description:
                Probabilistically use LCB, EI, or PI at every
                iteration
            - value: EIps
              description: Negative expected improvement per second
            - value: PIps
              description:
                Negative probability of improvement per second
        kappa:
          description:
            Degree to which variance in the predicted values is taken
            into account
          default: 1.96
          type: float
        xi:
          description:
            Improvement to seek over the previous best values
          default: 0.05
          type: float
        noise:
          description:
            Level of noise associated with the objective

            Use 'gaussian' if the objective returns noisy
            observations, otherwise specify the expected variance of
            the noise.
          default: gaussian
        prev-trials:
          description:
            Method used to select previous trials for suggestions
          default: batch
          choices:
            - value: batch
              description: Use trials generated by the batch run
            - value: sourcecode
              description: Use trials with the same source code
            - value: operation
              description: Use trials with the same operation name

    forest:
      description:
        Sequential optimization using decision trees.

        Refer to
        https://scikit-optimize.github.io/#skopt.forest_minimize for
        details on this algorithm and its flags.

      exec: ${python_exe} -um guild.plugins.skopt_forest_main
      flags:
        random-starts:
          description:
            Number of trials using random values before optimizing
          default: 3
          type: int
        kappa:
          description:
            Degree to which variance in the predicted values is
            taken into account
          default: 1.96
          type: float
        xi:
          description:
            Improvement to seek over the previous best values
          default: 0.05
          type: float
        prev-trials:
          description:
            Method used to select previous trials for suggestions
          default: batch
          choices:
            - value: batch
              description: Use trials generated by the batch run
            - value: sourcecode
              description: Use trials with the same source code
            - value: operation
              description: Use trials with the same operation name
    gbrt:
      description:
        Sequential optimization using gradient boosted regression
        trees.

        Refer to
        https://scikit-optimize.github.io/#skopt.gbrt_minimize for
        details on this algorithm and its flags.

      exec: ${python_exe} -um guild.plugins.skopt_gbrt_main
      flags:
        random-starts:
          description:
            Number of trials using random values before optimizing
          default: 3
          type: int
        kappa:
          description:
            Degree to which variance in the predicted values is taken
            into account
          default: 1.96
          type: float
        xi:
          description:
            Improvement to seek over the previous best values
          default: 0.05
          type: float
        prev-trials:
          description:
            Method used to select previous trials for suggestions
          default: batch
          choices:
            - value: batch
              description: Use trials generated by the batch run
            - value: sourcecode
              description: Use trials with the same source code
            - value: operation
              description: Use trials with the same operation name
    """
    )
    _apply_opdef_defaults(opdefs)
    return opdefs


def _apply_opdef_defaults(opdefs):
    defaults = {
        "flag-encoder": "guild.plugins.skopt:encode_flag_for_optimizer",
        "default-max-trials": 20,
        "delete-on-success": False,
        "can-stage-trials": False,
        "env": {
            "NO_OP_INTERRUPTED_MSG": "1",
        },
    }
    for opdef in opdefs.values():
        opdef.update({name: defaults[name] for name in defaults if name not in opdef})


###################################################################
# Flag encoders
###################################################################


def encode_flag_for_optimizer(val, flagdef):
    """Encodes a flag def for the range of supported skopt search spaces."""
    if flagdef.choices:
        return [c.value for c in flagdef.choices]
    if flagdef.min is not None and flagdef.max is not None:
        return _encode_function(flagdef, val)
    return val


def _encode_function(flagdef, val):
    assert flagdef.min is not None and flagdef.max is not None
    func_name = flagdef.distribution or "uniform"
    low = flag_util.encode_flag_val(flagdef.min)
    high = flag_util.encode_flag_val(flagdef.max)
    args = [low, high]
    if val is not None:
        initial = flag_util.encode_flag_val(val)
        args.append(initial)
    return f"{func_name}[{':'.join(args)}]"


###################################################################
# Plugin
###################################################################


class SkoptPlugin(pluginlib.Plugin):
    def resolve_model_op(self, opspec):
        if opspec in ("random", "skopt:random"):
            return SkoptModelProxy(), "random"
        if opspec in ("gp", "skopt:gp", "bayesian", "gaussian"):
            return SkoptModelProxy(), "gp"
        if opspec in ("forest", "skopt:forest"):
            return SkoptModelProxy(), "forest"
        if opspec in ("gbrt", "skopt:gbrt"):
            return SkoptModelProxy(), "gbrt"
        return None
