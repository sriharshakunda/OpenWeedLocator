import cv2
import image_pb2  # Import the generated protobuf file
import numpy as np

def deserialize_image(file_path):
    """Deserialize the image from a binary file using Protobuf."""
    # Read the serialized data from the file
    with open(file_path, "rb") as f:
        image_data = f.read()

    # Deserialize the data using Protobuf
    image_proto = image_pb2.ImageData()
    image_proto.ParseFromString(image_data)

    # Get the image data, width, and height
    image_bytes = image_proto.image
    width = image_proto.width
    height = image_proto.height
    format = image_proto.format  # Assuming format is 'BGRx'

    # Convert the byte data to a NumPy array
    image_np = np.frombuffer(image_bytes, dtype=np.uint8)

    # Reshape the array to an OpenCV image format (height, width, channels)
    if format == 'BGRx':
        # BGRx format is typically BGR with an extra padding byte, strip it if necessary
        image_np = image_np.reshape((height, width, 4))[:, :, :3]  # Remove the alpha channel
    else:
        # Adjust this section if you have other formats
        print(f"Unknown format: {format}")
        return None

    return image_np

def display_image(image_np):
    """Display the image using OpenCV."""
    # Create a window
    cv2.namedWindow("Deserialized Image", cv2.WINDOW_NORMAL)
    cv2.imshow("Deserialized Image", image_np)

    # Wait until a key is pressed
    cv2.waitKey(0)

    # Destroy all windows
    cv2.destroyAllWindows()

def main():
    # Path to the serialized image file
    file_path = "image_feed.bin"  # Replace with your serialized file path

    # Deserialize the image
    image_np = deserialize_image(file_path)

    # Display the image if deserialization was successful
    if image_np is not None:
        display_image(image_np)
    else:
        print("Failed to deserialize the image.")

if __name__ == "__main__":
    main()

