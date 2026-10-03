"""Shared test helpers."""
from conftest import EXAMPLES
from ilc.costs import PROFILES
from ilc.pipeline import compile_source

REVERSIBLE = """
system Reversible {
  stato a : bit
  stato b : bit
  stato tmp : bit { durata = until(result) }
  trasforma xor(a, b) -> tmp
  trasforma copy(tmp) -> result
  emit result
}
"""

RECOVERY = (EXAMPLES / "recovery.lang").read_text()
BOUNDARY = (EXAMPLES / "boundary.lang").read_text()

# y is produced by a non-exact transform and needed again after an idle gap; no bulk tier.
STOCH = """
system Stoch {
  componente sram { role = primary }
  componente nvm  { role = durable }
  flusso sram -> nvm
  flusso nvm -> sram
  stato a : u8 { durata = persistent }
  stato y : u8 { ACCEPT }
  trasforma add(a, a) -> y { regen = distributional }
  trasforma inc(y) -> u1
  trasforma not(u1) -> u2
  trasforma not(u2) -> u3
  trasforma xor(y, u3) -> z
  emit z
}
"""


def graph(src, cfg=None):
    return compile_source(src, "test.lang", cfg)


def example(name):
    return (EXAMPLES / f"{name}.lang").read_text()


def default_cfg():
    return PROFILES["abstract-default"]
