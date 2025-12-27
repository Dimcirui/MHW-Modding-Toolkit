from . import mhwi, mhws, re4

modules = [
    mhwi,
    mhws,
    re4,
]

def register():
    for mod in modules:
        mod.register()

def unregister():
    for mod in reversed(modules):
        mod.unregister()