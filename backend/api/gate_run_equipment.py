"""What a gate run is run *with*: the library directory it writes to, the gold sets
it reads, and the three reference agents it attacks.

Split out of `gate_runs.py`, which held the equipment, the record and the service in
one file. This is the equipment — three paths and a seam — and it is separable
because none of it knows a gate run exists. `seeded_library` is a function of two
directories, `shipped_agents` is a function of a model name, and `GateRunBench` is
the pair a deployment configures. A reader working out *whether this deployment can
run a gate at all* reads this module and stops.

**The reference agents may be absent, and then this bench states it.** They are test
equipment served by a different application (`backend/targets/reference`) and never
reach a user, so a deployment that does not ship them cannot run a gate. The
equipment is therefore a seam that can be *missing* — `shipped_agents` returns
`None` when the module is not importable — and the console reads the refusal and
offers no control rather than failing when one is pressed. That is why `Equipment`
is a callable rather than an import.

**Nothing here reads the environment**, which is asserted over every module of
`backend/api/` and which this module inherits by being one
(`test_no_module_of_the_api_reads_an_environment_of_its_own`). `DEPLOYED_LIBRARY` is
a mount point for that reason: a path a variable could point anywhere is a path a
redeploy can silently change.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path

from backend.bench.calibration import PlantNonce
from backend.bench.contract import TargetConfig

GOLDSET_DIR = Path(__file__).resolve().parents[1] / "goldset"
"""The hand-labelled transcripts a judged family's κ is measured against.

Read from the image rather than from the library's own directory, because a gold set
is not a case: it is the reference a judged family's reliability is measured on and
it is labelled before any user sees the bench (CONTEXT.md). A gate run writes to the
case records and never to these.
"""


DEPLOYED_LIBRARY = Path("/var/lib/agentaudit/cases")
"""Where a deployed bench keeps the case library a gate run may write to.

**One declared path, outside the image, and it is a decision rather than a
convenience.** A gate run's write-back is evidence: the decay series a retirement is
re-derived from, and the retirement itself. Written inside the container it would be
gone at the next redeploy, and a bench that had retired a case would come back with
it live again and no record that it ever went — which is the state a reader of the
library cannot detect. So the deployment mounts a volume here, `deployed_bench`
seeds it once from the image's own admitted library if it is empty, and a bench with
nothing mounted declares **no writable library** and runs no gate at all.

Not read from the environment, deliberately: no module of this package is an
environment reader (ADR-0020), and a path that could be pointed anywhere by a
variable is a path a redeploy can silently change. It is a mount point, which is the
one place a deployment already has to say something about storage.
"""


def seeded_library(mount: Path, seed: Path) -> Path | None:
    """The mounted case library, seeded once from the image, or `None` if none is
    mounted.

    Three states and they are three different facts. **No mount** is a deployment
    that declared no storage: it gets `None`, runs no gate, and says so — never a
    silent write into the image. **An empty mount** is a first boot against a fresh
    volume: the image's own admitted library is copied in once, because a bench whose
    library is empty has nothing to run and nothing to serve. **A mount with records
    in it** is the library this deployment has been accumulating, and it is left
    exactly as it is — a seed written over a series would erase the decay history
    every retirement is re-derived from, which is the one thing here that cannot be
    recomputed.

    Copied file by file rather than by any tree copy, so that what lands is case
    records and nothing else: no lease left behind by a previous run, no document,
    nothing that is not a `*.toml` this bench wrote itself.
    """
    if not mount.is_dir():
        return None
    if not any(mount.glob("*.toml")):
        for record in sorted(seed.glob("*.toml")):
            (mount / record.name).write_text(
                record.read_text(encoding="utf-8"), encoding="utf-8"
            )
    return mount


@dataclass(frozen=True)
class ServedAgents:
    """The three reference agents, served, and the roles they were served under.

    The roles are three named fields rather than an order, for the reason
    `read_gate` takes them as required keyword arguments: `D` is trivial minus
    hardened and is not symmetric, so a call site that could pass them positionally
    could invert the bench's central claim and report a broken instrument as a
    working one.
    """

    targets: tuple[TargetConfig, ...]
    plant: PlantNonce
    trivial: str
    weak: str
    hardened: str

    measured_the_field: bool
    """Whether the model these three ran on was the field, or a stub fixture.

    Answered by whatever served them, because that is what holds the `ModelConfig`,
    and carried here so that the write-back can record it on every reading it stores
    (ADR-0022). Not derived from the declared model string in this module: the answer
    is a fact about a closed `Provider` enum which lives in `backend/targets/`, and
    this module reaches that package through the equipment seam and an import that is
    allowed to fail — never at module scope.

    Required rather than defaulted, on the same terms as the three roles above: the
    permissive answer is the one that lets the rule retire a case, so equipment that
    could leave it out could retire a library on a run that spent nothing.
    """


Equipment = Callable[[], AbstractContextManager[ServedAgents]]
"""How a gate run gets hold of the three reference agents while it runs.

A callable that serves them and takes them down again, so that the equipment is a
seam rather than an import: it can be missing, which is the case a deployment that
ships no test equipment is in, and it can be substituted, which is how this is
tested without a model.
"""


def shipped_agents(model: str) -> Equipment | None:
    """The three reference agents this deployment ships, or `None` if it ships none.

    The import is inside the function and its failure is an answer rather than an
    error: `backend/targets/reference` is test equipment that never reaches a user,
    so a build that leaves it out is a legitimate deployment which cannot run a gate
    — and the console has to be able to say so rather than break on it.

    `model` is the reference agents' declared model, off the record that declares it
    (`DeclaredModels.calibration`), and never a literal here. The bearer token is
    issued inside `served`, once per gate run, because these endpoints exist for the
    length of one and a token minted at boot would outlive every run that used it.
    """
    try:
        from backend.targets.reference.hardened import HARDENED
        from backend.targets.reference.model import ModelConfig, measures_the_field
        from backend.targets.reference.operator import nonce_planter
        from backend.targets.reference.server import (
            ReferenceConfig,
            create_reference_app,
        )
        from backend.targets.reference.serving import serve
        from backend.targets.reference.tools import DECLARED_TOOL_NAMES
        from backend.targets.reference.trivial import TRIVIAL
        from backend.targets.reference.weak import WEAK
    except ImportError:
        return None

    @contextmanager
    def served() -> Iterator[ServedAgents]:
        """All three, on an ephemeral port, for the length of one gate run.

        All three and never fewer: `D` is trivial minus hardened and monotonicity is
        read across all three, so a gate on two agents is not a smaller gate but a
        different and undeclared one. There is no argument here that could ask for a
        subset.
        """
        auth_token = secrets.token_urlsafe(16)
        app = create_reference_app(
            ReferenceConfig(model=ModelConfig.parse(model), auth_token=auth_token)
        )
        with serve(app) as base_url:
            yield ServedAgents(
                measured_the_field=measures_the_field(ModelConfig.parse(model)),
                targets=tuple(
                    TargetConfig(
                        name=agent.name,
                        url=f"{base_url}/reference/{agent.name}/messages",
                        auth_token=auth_token,
                        agent_type="assistant",
                        # The reference agents expose their tool calls and declare
                        # the document tools, which is what makes scope creep and
                        # halt defeat measurable against them at all (ADR-0004).
                        exposes_tool_calls=True,
                        declared_tools=DECLARED_TOOL_NAMES,
                    )
                    for agent in (TRIVIAL, WEAK, HARDENED)
                ),
                plant=nonce_planter(base_url),
                trivial=TRIVIAL.name,
                weak=WEAK.name,
                hardened=HARDENED.name,
            )

    return served


@dataclass(frozen=True)
class GateRunBench:
    """What a gate run on this bench needs, and the two ways it may be absent.

    Its own record beside `BenchConfig` rather than four more fields on it, because
    none of this is what a *run* is measured with: a bench that can serve every
    route under `/runs` and cannot run a gate is a normal deployment, and a bench
    that can run a gate has said two extra things about itself.

    Both fields default to absent, which is what every bench in the test suite and
    every bench that declared nothing is: a gate run is the one operation on this
    surface that spends 830 calls and writes to the library, and it is not something
    a deployment gets by omission.
    """

    library: Path | None = None
    """The case library directory a gate run reads and writes back to.

    A directory and not the loaded cases, because the write-back is per record: the
    reading a retirement is re-derived from has to be on the case's own file
    (`retirement.store`). `None` is a bench that runs no gate, and it is the honest
    answer for a deployment with nothing durable to write to.
    """

    equipment: Equipment | None = None
    """How the three reference agents are served, or `None` where they are absent.

    Absent is not an error: they are test equipment that never reaches a user, so a
    deployment can legitimately not ship them, and the console states it and offers
    no start control.
    """
