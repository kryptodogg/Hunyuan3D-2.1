import trimesh
import pygltflib
import numpy as np
from PIL import Image
import base64
import io


def combine_metallic_roughness(metallic_input, roughness_input):
    """
    将metallic和roughness贴图合并为一张贴图
    GLB格式要求metallic在B通道，roughness在G通道
    Returns: io.BytesIO containing the PNG image.
    """
    def load_image(input_src):
        if isinstance(input_src, str):
            return Image.open(input_src).convert("L")
        elif isinstance(input_src, (bytes, io.BytesIO)):
            return Image.open(input_src).convert("L")
        elif isinstance(input_src, Image.Image):
            return input_src.convert("L")
        else:
            raise ValueError(f"Unknown image input type: {type(input_src)}")

    # 加载贴图
    metallic_img = load_image(metallic_input)
    roughness_img = load_image(roughness_input)

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

    # 转回PIL图像并保存到BytesIO
    combined = Image.fromarray(combined_array)
    output = io.BytesIO()
    combined.save(output, format="PNG")
    output.seek(0)
    return output


def create_glb_with_pbr_materials(obj_path, textures_dict, output_path):
    """
    使用pygltflib创建包含完整PBR材质的GLB文件

    This optimized version performs in-memory operations to avoid disk I/O and race conditions.

    textures_dict = {
        'albedo': 'path/to/albedo.png' or bytes/BytesIO,
        'metallic': 'path/to/metallic.png' or bytes/BytesIO,
        'roughness': 'path/to/roughness.png' or bytes/BytesIO,
        'normal': 'path/to/normal.png',  # 可选
        'ao': 'path/to/ao.png'  # 可选
    }
    """
    # 1. 加载OBJ文件
    mesh = trimesh.load(obj_path)

    # 2. 先导出为临时GLB (In-Memory)
    glb_buffer = io.BytesIO()
    mesh.export(glb_buffer, file_type='glb')
    glb_buffer.seek(0)

    # 3. 加载GLB文件进行材质编辑
    gltf = pygltflib.GLTF2.load_from_bytes(glb_buffer.read())

    # 4. 准备纹理数据
    def image_to_data_uri(image_source):
        """将图像转换为data URI"""
        if isinstance(image_source, str):
            with open(image_source, "rb") as f:
                data = f.read()
        elif isinstance(image_source, io.BytesIO):
            data = image_source.getvalue()
        elif isinstance(image_source, bytes):
            data = image_source
        else:
            raise ValueError(f"Unknown image source type: {type(image_source)}")

        encoded = base64.b64encode(data).decode()
        return f"data:image/png;base64,{encoded}"

    # 5. 合并metallic和roughness
    if "metallic" in textures_dict and "roughness" in textures_dict:
        # Returns BytesIO object
        mr_bytes = combine_metallic_roughness(textures_dict["metallic"], textures_dict["roughness"])
        textures_dict["metallicRoughness"] = mr_bytes

    # 6. 添加图像到GLTF
    images = []
    textures = []

    texture_mapping = {
        "albedo": "baseColorTexture",
        "metallicRoughness": "metallicRoughnessTexture",
        "normal": "normalTexture",
        "ao": "occlusionTexture",
    }

    for tex_type, tex_path in textures_dict.items():
        if tex_type in texture_mapping and tex_path:
            # 添加图像
            image = pygltflib.Image(uri=image_to_data_uri(tex_path))
            images.append(image)

            # 添加纹理
            texture = pygltflib.Texture(source=len(images) - 1)
            textures.append(texture)

    # 7. 创建PBR材质
    pbr_metallic_roughness = pygltflib.PbrMetallicRoughness(
        baseColorFactor=[1.0, 1.0, 1.0, 1.0], metallicFactor=1.0, roughnessFactor=1.0
    )

    # 设置纹理索引
    texture_index = 0
    if "albedo" in textures_dict:
        pbr_metallic_roughness.baseColorTexture = pygltflib.TextureInfo(index=texture_index)
        texture_index += 1

    if "metallicRoughness" in textures_dict:
        pbr_metallic_roughness.metallicRoughnessTexture = pygltflib.TextureInfo(index=texture_index)
        texture_index += 1

    # 创建材质
    material = pygltflib.Material(name="PBR_Material", pbrMetallicRoughness=pbr_metallic_roughness)

    # 添加法线贴图
    if "normal" in textures_dict:
        material.normalTexture = pygltflib.NormalTextureInfo(index=texture_index)
        texture_index += 1

    # 添加AO贴图
    if "ao" in textures_dict:
        material.occlusionTexture = pygltflib.OcclusionTextureInfo(index=texture_index)

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
