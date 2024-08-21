#include <gst/gst.h>
#include <gst/video/videooverlay.h>
#include <gtk/gtk.h>
#include <iostream>

// Function to handle errors and EOS in the GStreamer bus
static gboolean bus_call(GstBus *bus, GstMessage *msg, gpointer data) {
    GMainLoop *loop = (GMainLoop *)data;

    switch (GST_MESSAGE_TYPE(msg)) {
        case GST_MESSAGE_ERROR: {
            GError *err;
            gchar *debug;
            gst_message_parse_error(msg, &err, &debug);
            std::cerr << "Error: " << err->message << std::endl;
            g_error_free(err);
            g_free(debug);
            g_main_loop_quit(loop);
            break;
        }
        case GST_MESSAGE_EOS:
            std::cout << "End of stream" << std::endl;
            g_main_loop_quit(loop);
            break;
        default:
            break;
    }

    return TRUE;
}

int main(int argc, char *argv[]) {
    // Initialize GTK
    gtk_init(&argc, &argv);

    // Initialize GStreamer
    gst_init(&argc, &argv);

    // Create the GTK window
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(window), "GStreamer Video Window");
    gtk_window_set_default_size(GTK_WINDOW(window), 1280, 720);

    // Set up the window close signal
    g_signal_connect(window, "destroy", G_CALLBACK(gtk_main_quit), NULL);

    // Create a GTK drawing area for GStreamer to render the video
    GtkWidget *drawing_area = gtk_drawing_area_new();
    gtk_container_add(GTK_CONTAINER(window), drawing_area);
    gtk_widget_show_all(window);

    // Create GStreamer pipeline string
    const char *pipeline_str = 
        "nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int)1280, height=(int)720, format=(string)NV12, framerate=(fraction)30/1 ! "
        "nvvidconv flip-method=0 ! video/x-raw, format=(string)BGRx ! videoconvert ! gtksink name=videosink";

    // Create the pipeline
    GstElement *pipeline = gst_parse_launch(pipeline_str, NULL);

    if (!pipeline) {
        std::cerr << "Failed to create pipeline." << std::endl;
        return -1;
    }

    // Retrieve the gtksink element and set it to use the drawing area for rendering
    GstElement *videosink = gst_bin_get_by_name(GST_BIN(pipeline), "videosink");
    if (!videosink) {
        std::cerr << "Failed to retrieve the gtksink element." << std::endl;
        gst_object_unref(pipeline);
        return -1;
    }

    // Set the GTK widget for gtksink
    GstVideoOverlay *overlay = GST_VIDEO_OVERLAY(videosink);
    gst_video_overlay_set_widget(overlay, GTK_WIDGET(drawing_area));

    // Add a bus to watch for errors and EOS
    GstBus *bus = gst_element_get_bus(pipeline);
    GMainLoop *loop = g_main_loop_new(NULL, FALSE);
    gst_bus_add_watch(bus, bus_call, loop);
    gst_object_unref(bus);

    // Start playing the pipeline
    gst_element_set_state(pipeline, GST_STATE_PLAYING);

    // Run the GTK main loop
    g_main_loop_run(loop);

    // Clean up and free resources
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    g_main_loop_unref(loop);

    return 0;
}

