#include <gst/gst.h>
#include <iostream>

// Function to test GStreamer elements
bool test_gstreamer_pipeline() {
    // Initialize GStreamer
    gst_init(NULL, NULL);

    // Create the GStreamer pipeline
    GstElement *pipeline = gst_pipeline_new("test-pipeline");

    // Create GStreamer elements
    GstElement *source = gst_element_factory_make("videotestsrc", "source");
    GstElement *convert = gst_element_factory_make("videoconvert", "convert");
    GstElement *sink = gst_element_factory_make("xvimagesink", "sink");

    if (!pipeline || !source || !convert || !sink) {
        std::cerr << "Failed to create GStreamer elements." << std::endl;
        return false;
    }

    // Add elements to the pipeline
    gst_bin_add_many(GST_BIN(pipeline), source, convert, sink, NULL);

    // Link the elements together
    if (!gst_element_link_many(source, convert, sink, NULL)) {
        std::cerr << "Failed to link elements." << std::endl;
        gst_object_unref(pipeline);
        return false;
    }

    // Set properties for the source (test pattern, framerate, etc.)
    g_object_set(G_OBJECT(source), "pattern", 0, NULL);  // 0 is the "smpte" pattern

    // Start playing the pipeline
    gst_element_set_state(pipeline, GST_STATE_PLAYING);

    // Wait until error or EOS
    GstBus *bus = gst_element_get_bus(pipeline);
    GstMessage *msg;
    bool running = true;

    while (running) {
        msg = gst_bus_timed_pop_filtered(bus, GST_CLOCK_TIME_NONE,
                                         static_cast<GstMessageType>(GST_MESSAGE_ERROR | GST_MESSAGE_EOS));

        if (msg != NULL) {
            GError *err;
            gchar *debug_info;

            switch (GST_MESSAGE_TYPE(msg)) {
                case GST_MESSAGE_ERROR:
                    gst_message_parse_error(msg, &err, &debug_info);
                    std::cerr << "Error received from element " << GST_OBJECT_NAME(msg->src) << ": " << err->message << std::endl;
                    std::cerr << "Debugging information: " << (debug_info ? debug_info : "none") << std::endl;
                    g_clear_error(&err);
                    g_free(debug_info);
                    running = false;
                    break;
                case GST_MESSAGE_EOS:
                    std::cout << "End-Of-Stream reached." << std::endl;
                    running = false;
                    break;
                default:
                    std::cerr << "Unexpected message received." << std::endl;
                    break;
            }
            gst_message_unref(msg);
        }
    }

    // Free resources
    gst_object_unref(bus);
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);

    return true;
}

int main(int argc, char *argv[]) {
    if (test_gstreamer_pipeline()) {
        std::cout << "GStreamer pipeline tested successfully." << std::endl;
    } else {
        std::cerr << "GStreamer pipeline test failed." << std::endl;
    }
    return 0;
}

