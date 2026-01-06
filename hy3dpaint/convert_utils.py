import trimesh
import pygltflib
import numpy as np
from PIL import Image
import base64
import io


def combine_metallic_roughness(metallic_path, roughness_path, output_path=None):
    """
    Combine metallic and roughness maps into a single texture.
    GLB format requires metallic in B channel, roughness in G channel.

    Args:
        metallic_path: Path to metallic texture
        roughness_path: Path to roughness texture
        output_path: Optional path to save the combined image. If None, returns PIL Image.

    Returns:
        Path to saved image if output_path is provided, else PIL Image object.
    """
    # Load textures
    metallic_img = Image.open(metallic_path).convert("L")  # Convert to grayscale
    roughness_img = Image.open(roughness_path).convert("L")  # Convert to grayscale

    # Ensure consistent dimensions
    if metallic_img.size != roughness_img.size:
        roughness_img = roughness_img.resize(metallic_img.size)

    # Create RGB image
    width, height = metallic_img.size

    # Convert to numpy arrays for manipulation
    metallic_array = np.array(metallic_img)
    roughness_array = np.array(roughness_img)

    # Create combined array (R, G, B) = (AO, Roughness, Metallic)
    combined_array = np.zeros((height, width, 3), dtype=np.uint8)
    combined_array[:, :, 0] = 255  # R channel: AO (white if no AO)
    combined_array[:, :, 1] = roughness_array  # G channel: Roughness
    combined_array[:, :, 2] = metallic_array  # B channel: Metallic

    # Convert back to PIL image
    combined = Image.fromarray(combined_array)

    if output_path:
        combined.save(output_path)
        return output_path
    return combined


def create_glb_with_pbr_materials(obj_path, textures_dict, output_path):
    """
    Create a GLB file with full PBR materials using pygltflib, optimized for memory usage.

    textures_dict = {
        'albedo': 'path/to/albedo.png',
        'metallic': 'path/to/metallic.png',
        'roughness': 'path/to/roughness.png',
        'normal': 'path/to/normal.png',  # Optional
        'ao': 'path/to/ao.png'  # Optional
    }
    """
    # 1. Load OBJ file
    mesh = trimesh.load(obj_path)

    # 2. Export to GLB in memory (avoiding temp.glb disk write)
    glb_bytes = mesh.export(file_type='glb')

    # 3. Load GLB from bytes
    gltf = pygltflib.GLTF2().load_from_bytes(glb_bytes)

    # 4. Helper to convert image source to data URI
    def image_to_data_uri(image_source):
        """Convert image (path or bytes) to data URI"""
        if isinstance(image_source, str):
            with open(image_source, "rb") as f:
                image_data = f.read()
        elif isinstance(image_source, bytes):
            image_data = image_source
        else:
            raise ValueError("Unsupported image source type")

        encoded = base64.b64encode(image_data).decode()
        return f"data:image/png;base64,{encoded}"

    # 5. Combine metallic and roughness in memory
    mr_image_bytes = None
    if "metallic" in textures_dict and "roughness" in textures_dict:
        # Generate in memory, returning PIL Image
        mr_image = combine_metallic_roughness(textures_dict["metallic"], textures_dict["roughness"], output_path=None)

        # Convert PIL Image to bytes
        with io.BytesIO() as output:
            mr_image.save(output, format="PNG")
            mr_image_bytes = output.getvalue()

        # Mark as ready for processing
        textures_dict["metallicRoughness"] = "IN_MEMORY"

    # 6. Add images to GLTF
    images = []
    textures = []

    texture_mapping = {
        "albedo": "baseColorTexture",
        "metallicRoughness": "metallicRoughnessTexture",
        "normal": "normalTexture",
        "ao": "occlusionTexture",
    }

    # Track mapping from texture type to index in the GLTF textures array
    tex_type_to_index = {}

    for tex_type, tex_path in textures_dict.items():
        if tex_type in texture_mapping and tex_path:
             # Generate URI
            uri = ""
            if tex_type == "metallicRoughness" and tex_path == "IN_MEMORY":
                if mr_image_bytes:
                    uri = image_to_data_uri(mr_image_bytes)
            else:
                 # Handle regular file paths (including metallicRoughness if provided directly)
                 uri = image_to_data_uri(tex_path)

            if uri:
                image = pygltflib.Image(uri=uri)
                images.append(image)
                texture = pygltflib.Texture(source=len(images) - 1)
                textures.append(texture)
                tex_type_to_index[tex_type] = len(textures) - 1

    # 7. Create PBR Material
    pbr_metallic_roughness = pygltflib.PbrMetallicRoughness(
        baseColorFactor=[1.0, 1.0, 1.0, 1.0], metallicFactor=1.0, roughnessFactor=1.0
    )

    if "albedo" in tex_type_to_index:
        pbr_metallic_roughness.baseColorTexture = pygltflib.TextureInfo(index=tex_type_to_index["albedo"])

    if "metallicRoughness" in tex_type_to_index:
        pbr_metallic_roughness.metallicRoughnessTexture = pygltflib.TextureInfo(index=tex_type_to_index["metallicRoughness"])

    # Create Material
    material = pygltflib.Material(name="PBR_Material", pbrMetallicRoughness=pbr_metallic_roughness)

    # Add Normal Map
    if "normal" in tex_type_to_index:
        material.normalTexture = pygltflib.NormalTextureInfo(index=tex_type_to_index["normal"])

    # Add AO Map
    if "ao" in tex_type_to_index:
        material.occlusionTexture = pygltflib.OcclusionTextureInfo(index=tex_type_to_index["ao"])

    # 8. Update GLTF
    gltf.images = images
    gltf.textures = textures
    gltf.materials = [material]

    # Ensure mesh uses material
    if gltf.meshes:
        for primitive in gltf.meshes[0].primitives:
            primitive.material = 0

    # 9. Save final GLB
    gltf.save(output_path)
    # print(f"PBR GLB file saved: {output_path}")
