"""
The ``yafs`` module is the main component who perform the simulation.

The following tables list all of the available components in this module.

{toc}

"""
from pkgutil import extend_path
from VRGameFog_IFogSim_WL import placement_Cluster_Edge
from VRGameFog_IFogSim_WL import selection_multipleDeploys 


def compile_toc(entries, section_marker='='):
    """Compiles a list of sections with objects into sphinx formatted
    autosummary directives."""
    toc = ''
    for section, objs in entries:
        toc += '\n\n%s\n%s\n\n' % (section, section_marker * len(section))

        toc += '.. autosummary::\n\n'

        for obj in objs:
            toc += '    ~%s.%s\n' % (obj.__module__, obj.__name__)
    return toc


toc = (
    ('placement_Cluster_Edge'),
    ('selection_multipleDeploys'),
)


# Use the toc to keep the documentation and the implementation in sync.
if __doc__:
    __doc__ = __doc__.format(toc=compile_toc(toc))

__all__ = [obj.__name__ for section, objs in toc for obj in objs]

__path__ = extend_path(__path__, __name__)
__version__ = '0.1'
