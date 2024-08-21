#include <gst/gst.h>
#include <gst/app/gstappsink.h>
#include <iostream>
#include <fstream>
#include "image.pb.h"  // Include generated protobuf header

// Function to convert GStreamer sample to Protobuf
bool convert_to_protobuf(GstSample *sample, ImageData &image_data) {
    GstBuffer *buffer = gst_sample_get_buffer(sample);
    GstCaps *caps = gst_sample_get_caps(sample);
    GstStructure *s = gst_caps_get_structure(caps, 0);

    int width, height;
    gst_structure_get_int(s, "width", &width);
    gst_structure_get_int(s, "height", &height);

    GstMapInfo map;
    if (gst_buffer_map(buffer, &map, GST_MAP_READ)) {
        image_data.set_image(map.data, map.size); // Set image data
        image_data.set_width(width);
        image_data.set_height(height);
        image_data.set_format("BGRx");  // Use appropriate format
        gst_buffer_unmap(buffer, &map);
        return true;
    }
    return false;
}

int main(int argc, char *argv[]) {
    gst_init(&argc, &argv);
    GOOGLE_PROTOBUF_VERIFY_VERSION;

    // Create GStreamer pipeline
    const char *pipeline_str =
        "nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int)480, height=(int)360, format=(string)NV12, framerate=(fraction)10/1 ! "
        "nvvidconv flip-method=0 ! video/x-raw, format=(string)BGRx ! videoconvert ! appsink name=sink";

    GstElement *pipeline = gst_parse_launch(pipeline_str, NULL);
    GstElement *appsink = gst_bin_get_by_name(GST_BIN(pipeline), "sink");

    if (!pipeline || !appsink) {
        std::cerr << "Failed to create pipeline or appsink." << std::endl;
        return -1;
    }

    // Set appsink properties
    gst_app_sink_set_emit_signals((GstAppSink *)appsink, true);
    gst_app_sink_set_drop((GstAppSink *)appsink, true);
    gst_app_sink_set_max_buffers((GstAppSink *)appsink, 1);

    // Start pipeline
    gst_element_set_state(pipeline, GST_STATE_PLAYING);

    // Capture frames and serialize them
    while (true) {
        GstSample *sample = gst_app_sink_pull_sample(GST_APP_SINK(appsink));
        if (sample) {
            ImageData image_data;
            if (convert_to_protobuf(sample, image_data)) {
                // Serialize to file or send over network
                std::ofstream output("image_feed.bin", std::ios::out | std::ios::binary);
                if (image_data.SerializeToOstream(&output)) {
                    std::cout << "Image serialized successfully." << std::endl;
                } else {
                    std::cerr << "Failed to serialize image." << std::endl;
                }
                output.close();
            }
            gst_sample_unref(sample);
        } else {
            std::cerr << "Failed to pull sample." << std::endl;
        }
    }

    // Clean up
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    google::protobuf::ShutdownProtobufLibrary();

    return 0;
}

