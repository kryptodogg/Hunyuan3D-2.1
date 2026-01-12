import trimesh
import pygltflib
import numpy as np
from PIL import Image
import base64
import io


def combine_metallic_roughness(metallic_path, roughness_path):
    """
    将metallic和roughness贴图合并为一张贴图
    GLB格式要求metallic在B通道，roughness在G通道
    Returns: PIL.Image
    """
    # 加载贴图
    metallic_img = Image.open(metallic_path).convert("L")  # 转为灰度
    roughness_img = Image.open(roughness_path).convert("L")  # 转为灰度

    # 确保尺寸一致
    if metallic_img.size != roughness_img.size:
        roughness_img = roughness_img.resize(metallic_img.size)

    # 创建RGB图像
    width, height = metallic_img.size

    # 转为numpy数组便于操作
    metallic_array = np.array(metallic_img)
    roughness_array = np.array(roughness_img)

    # 创建合并的数组 (R, G, B) = (AO, Roughness, Metallic)
    combined_array = np.zeros((height, width, 3), dtype=np.uint8)
    combined_array[:, :, 0] = 255  # R通道：AO (如果没有AO贴图，设为白色)
    combined_array[:, :, 1] = roughness_array  # G通道：Roughness
    combined_array[:, :, 2] = metallic_array  # B通道：Metallic

    # 转回PIL图像
    return Image.fromarray(combined_array)


def image_to_data_uri(image_source):
    """
    将图像转换为data URI
    Args:
        image_source: 文件路径(str) 或 PIL.Image 对象
    """
    if isinstance(image_source, str):
        with open(image_source, "rb") as f:
            image_data = f.read()
    elif isinstance(image_source, Image.Image):
        buffered = io.BytesIO()
        image_source.save(buffered, format="PNG")
        image_data = buffered.getvalue()
    else:
        raise ValueError(f"Unsupported image source type: {type(image_source)}")

    encoded = base64.b64encode(image_data).decode()
    return f"data:image/png;base64,{encoded}"


def create_glb_with_pbr_materials(obj_path, textures_dict, output_path):
    """
    使用pygltflib创建包含完整PBR材质的GLB文件

    textures_dict = {
        'albedo': 'path/to/albedo.png',
        'metallic': 'path/to/metallic.png',
        'roughness': 'path/to/roughness.png',
        'normal': 'path/to/normal.png',  # 可选
        'ao': 'path/to/ao.png'  # 可选
    }
    """
    # 1. 加载OBJ文件
    mesh = trimesh.load(obj_path)

    # 2. 导出为内存中的GLB
    # trimesh export accepts a file-like object
    glb_buffer = io.BytesIO()
    mesh.export(glb_buffer, file_type='glb')
    glb_buffer.seek(0)
    glb_bytes = glb_buffer.read()

    # 3. 加载GLB文件进行材质编辑
    gltf = pygltflib.GLTF2().load_from_bytes(glb_bytes)

    # 4. 准备纹理数据
    # Moved image_to_data_uri to module level for cleaner code

    # 5. 合并metallic和roughness
    mr_image = None
    if "metallic" in textures_dict and "roughness" in textures_dict:
        # Use in-memory image
        mr_image = combine_metallic_roughness(textures_dict["metallic"], textures_dict["roughness"])
        # We don't save it to disk anymore

    # 6. 添加图像到GLTF
    images = []
    textures = []

    texture_mapping = {
        "albedo": "baseColorTexture",
        # "metallicRoughness": "metallicRoughnessTexture", # Handle separately
        "normal": "normalTexture",
        "ao": "occlusionTexture",
    }

    # Helper to add texture
    def add_texture(source, tex_type_key=None):
        uri = image_to_data_uri(source)
        image = pygltflib.Image(uri=uri)
        images.append(image)
        texture = pygltflib.Texture(source=len(images) - 1)
        textures.append(texture)
        return len(textures) - 1

    # Add standard textures
    texture_indices = {}

    for tex_type, tex_path in textures_dict.items():
        if tex_type in texture_mapping and tex_path:
            texture_indices[tex_type] = add_texture(tex_path)

    # Add combined metallic/roughness if available
    if mr_image:
        texture_indices["metallicRoughness"] = add_texture(mr_image)

    # 7. 创建PBR材质
    pbr_metallic_roughness = pygltflib.PbrMetallicRoughness(
        baseColorFactor=[1.0, 1.0, 1.0, 1.0], metallicFactor=1.0, roughnessFactor=1.0
    )

    if "albedo" in texture_indices:
        pbr_metallic_roughness.baseColorTexture = pygltflib.TextureInfo(index=texture_indices["albedo"])

    if "metallicRoughness" in texture_indices:
        pbr_metallic_roughness.metallicRoughnessTexture = pygltflib.TextureInfo(index=texture_indices["metallicRoughness"])

    # 创建材质
    material = pygltflib.Material(name="PBR_Material", pbrMetallicRoughness=pbr_metallic_roughness)

    # 添加法线贴图
    if "normal" in texture_indices:
        material.normalTexture = pygltflib.NormalTextureInfo(index=texture_indices["normal"])

    # 添加AO贴图
    if "ao" in texture_indices:
        material.occlusionTexture = pygltflib.OcclusionTextureInfo(index=texture_indices["ao"])

    # 8. 更新GLTF
    gltf.images = images
    gltf.textures = textures
    gltf.materials = [material]

    # 确保mesh使用材质
    if gltf.meshes:
        for primitive in gltf.meshes[0].primitives:
            primitive.material = 0

    # 9. 保存最终GLB
    gltf.save(output_path)
    print(f"PBR GLB文件已保存: {output_path}")
