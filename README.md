# Modding Toolkit (Blender Addon)

A comprehensive Blender toolkit designed specifically for modding Monster Hunter World: Iceborne (MHWI), Monster Hunter Wilds (MHWs), and Resident Evil 4 Remake (RE4).

**Supported Versions**:
# Requirements
* [Blender 4.x (4.3)](https://www.blender.org/download/)
* Blender 3.x are still pending testing.


## Core Features

### 1. Universal Skeleton Converter
Convert any source model to any target game format using customizable JSON presets.

* **X -> Y Architecture**: Define your source (X) and target (Y) freely.
    * **Source (X)**: VRChat, MMD, Endfield, or your custom ripped models.
    * **Target (Y)**: MHWI, MHW: Wilds, RE4 Remake.
* **Intelligent Mapping**:
    * **Weight Merging**: Automatically merges auxiliary bones (Twist, Corrective, Helpers) into the main bone.
    * **One-Click Snap**: Aligns your model's skeleton to the target game's instantly.
    * **Direct Convert**: Renames vertex groups directly on the mesh without needing to touch the armature.

### 2. Visual Preset Editor
A built-in GUI editor to create your own mappings without writing a single line of code.
* **Pick & Click**: Select a bone in the 3D view and click to assign it.
* **Batch Aux Adding**: Select multiple twist bones and add them as weight sources in one click.
* **Smart Mirror**: Automatically generates Right-side mappings from the Left side.

### 3. Game-Specific Modules
Specialized tools for tasks that cannot be handled by simple mapping.

* **MHWI (Iceborne)**:
    * **Non-Physics Align**: Aligns mod skeletons to the game skeleton while intelligently preserving the physics bones (150~245).
* **RE4 (Remake)**:
    * **FakeBone System**: A complete toolset to generate, align, and merge the complex "FakeBone" (End bone) that resolve CG character distortion issues.

### 4. General Utilities
* **Roll Zero**: Recursively resets bone rolls to 0 for cleaner rigging. Non-zero roll causes performance issues in the RE engine's physical bones.
* **Add Tail**: Add end bones to the selected bones.
* **Mirror X**: Symmetrizes bone transforms from selected +X bone to -X bone.
* **Chain Simplification**: Optimizes physics chains by removing every other bone and merging weights.

---

## Installation & Update

1.  Download the **ZIP** file from the Releases page.
2.  In Blender, go to `Edit > Preferences > Add-ons`.
3.  Click **Install**, select the ZIP, and enable **Modding Toolkit**.
