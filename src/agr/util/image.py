from wand.image import Image


def append_images_horizontally(images: list[str], out_path: str):
    final_width = 0
    max_height = 0

    # Get total width and max height
    img_objects = []
    for img_path in images:
        img = Image(filename=img_path)
        img_objects.append(img)
        final_width += img.width
        max_height = max(max_height, img.height)

    # Create a new image with the combined dimensions
    final_image = Image(width=final_width, height=max_height)

    # Compose images
    x_offset = 0
    for img in img_objects:
        final_image.composite(img, left=x_offset, top=0)
        x_offset += img.width

    # Save the appended image
    final_image.save(filename=out_path)
