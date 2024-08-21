#include <gst/gst.h>
#include <iostream>

// Function to create a GStreamer pipeline for displaying two identical video feeds side by side
GstElement* create_pipeline(const std::string& video_device) {
    // Create the GStreamer pipeline
    GstElement *pipeline = gst_pipeline_new("dual-feed-pipeline");

    // Create elements for the camera source
    GstElement *source = gst_element_factory_make("v4l2src", "camera-source");
    GstElement *tee = gst_element_factory_make("tee", "tee");
    GstElement *queue1 = gst_element_factory_make("queue", "queue1");
    GstElement *convert1 = gst_element_factory_make("videoconvert", "convert1");
    GstElement *scale1 = gst_element_factory_make("videoscale", "scale1");
    GstElement *box1 = gst_element_factory_make("videobox", "box1");
    
    GstElement *queue2 = gst_element_factory_make("queue", "queue2");
    GstElement *convert2 = gst_element_factory_make("videoconvert", "convert2");
    GstElement *scale2 = gst_element_factory_make("videoscale", "scale2");
    GstElement *box2 = gst_element_factory_make("videobox", "box2");
    
    GstElement *compositor = gst_element_factory_make("compositor", "compositor");
    GstElement *sink = gst_element_factory_make("xvimagesink", "sink");

    if (!pipeline || !source || !tee || !queue1 || !convert1 || !scale1 || !box1 ||
        !queue2 || !convert2 || !scale2 || !box2 || !compositor || !sink) {
        std::cerr << "Failed to create GStreamer elements. Make sure all plugins are installed." << std::endl;
        return nullptr;
    }

    // Set the device property for the camera source
    g_object_set(G_OBJECT(source), "device", video_device.c_str(), NULL);

    // Set properties for video positioning using videobox
    g_object_set(G_OBJECT(box1), "border-alpha", 0, "left", -320, NULL); // Position first video to the left
    g_object_set(G_OBJECT(box2), "border-alpha", 0, "left", 320, NULL);  // Position second video to the right

    // Add elements to the pipeline
    gst_bin_add_many(GST_BIN(pipeline), source, tee, queue1, convert1, scale1, box1,
                     queue2, convert2, scale2, box2, compositor, sink, NULL);

    // Link the source to the tee
    if (!gst_element_link(source, tee)) {
        std::cerr << "Failed to link source to tee." << std::endl;
        gst_object_unref(pipeline);
        return nullptr;
    }

    // Link the elements for the first branch with caps filter
    GstCaps *caps = gst_caps_from_string("video/x-raw, format=I420, width=640, height=480");
    if (!gst_element_link_many(queue1, convert1, scale1, NULL) ||
        !gst_element_link_filtered(scale1, box1, caps) ||
        !gst_element_link(box1, compositor)) {
        std::cerr << "Failed to link elements for the first branch." << std::endl;
        gst_object_unref(pipeline);
        return nullptr;
    }

    // Link the elements for the second branch with caps filter
    if (!gst_element_link_many(queue2, convert2, scale2, NULL) ||
        !gst_element_link_filtered(scale2, box2, caps) ||
        !gst_element_link(box2, compositor)) {
        std::cerr << "Failed to link elements for the second branch." << std::endl;
        gst_object_unref(pipeline);
        return nullptr;
    }

    // Release caps reference
    gst_caps_unref(caps);

    // Link tee to queues
    GstPad *tee_src_pad1 = gst_element_get_request_pad(tee, "src_%u");
    GstPad *queue1_sink_pad = gst_element_get_static_pad(queue1, "sink");
    GstPad *tee_src_pad2 = gst_element_get_request_pad(tee, "src_%u");
    GstPad *queue2_sink_pad = gst_element_get_static_pad(queue2, "sink");

    if (gst_pad_link(tee_src_pad1, queue1_sink_pad) != GST_PAD_LINK_OK ||
        gst_pad_link(tee_src_pad2, queue2_sink_pad) != GST_PAD_LINK_OK) {
        std::cerr << "Failed to link tee to queues." << std::endl;
        gst_object_unref(pipeline);
        return nullptr;
    }

    gst_object_unref(tee_src_pad1);
    gst_object_unref(queue1_sink_pad);
    gst_object_unref(tee_src_pad2);
    gst_object_unref(queue2_sink_pad);

    // Link the compositor to the sink
    if (!gst_element_link(compositor, sink)) {
        std::cerr << "Failed to link compositor to sink." << std::endl;
        gst_object_unref(pipeline);
        return nullptr;
    }

    return pipeline;
}

int main(int argc, char *argv[]) {
    // Initialize GStreamer
    gst_init(&argc, &argv);

    // Define the video device (e.g., "/dev/video0")
    std::string video_device = "/dev/video0"; // Replace with your actual video device

    // Create the pipeline
    GstElement *pipeline = create_pipeline(video_device);
    if (!pipeline) {
        return -1;
    }

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

    return 0;
}

