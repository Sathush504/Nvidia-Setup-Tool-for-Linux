/*
 * NVIDIA GPU Setup Tool - Native C Application for Linux
 * 
 * A user-friendly GUI application for installing NVIDIA drivers and CUDA toolkit
 * Built with GTK3 for modern Linux desktop environments
 * 
 * Features:
 * - Automatic NVIDIA GPU detection
 * - Driver installation with progress tracking
 * - CUDA toolkit installation and environment setup
 * - Real-time status updates and logging
 * - System verification and error handling
 * - Improved distro compatibility and secure sudo handling
 * 
 * Compilation:
 * gcc -o nvidia-setup-tool nvidia_setup.c `pkg-config --cflags --libs gtk+-3.0` -lpthread
 * 
 * Dependencies:
 * - GTK3 development libraries
 * - pthread library
 * - Standard Linux utilities (lspci, apt-get, lsb-release, etc.)
 */

#include <gtk/gtk.h>
#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <pthread.h>
#include <errno.h>
#include <time.h>

// Application constants
#define APP_TITLE "NVIDIA GPU Setup Tool"
#define APP_VERSION "1.1"
#define MAX_CMD_OUTPUT 8192
#define MAX_LOG_LINES 1000
#define DETECTION_DELAY_NS 500000000 // 0.5 seconds

// Status types
typedef enum {
    STATUS_UNKNOWN,
    STATUS_SUCCESS,
    STATUS_WARNING,
    STATUS_ERROR,
    STATUS_INFO
} StatusType;

// System detection results
typedef struct {
    gboolean gpu_detected;
    gchar *gpu_info;
    gboolean driver_installed;
    gchar *driver_info;
    gboolean cuda_installed;
    gchar *cuda_info;
    gchar *distro_codename;
} SystemInfo;

// Application state
typedef struct {
    GtkWidget *main_window;
    GtkWidget *gpu_status_label;
    GtkWidget *driver_status_label;
    GtkWidget *cuda_status_label;
    GtkWidget *gpu_icon_label;
    GtkWidget *driver_icon_label;
    GtkWidget *cuda_icon_label;
    GtkWidget *install_driver_check;
    GtkWidget *install_cuda_check;
    GtkWidget *detect_button;
    GtkWidget *install_button;
    GtkWidget *progress_bar;
    GtkWidget *progress_label;
    GtkWidget *console_textview;
    GtkWidget *progress_frame;
    GtkTextBuffer *console_buffer;
    
    SystemInfo system_info;
    gboolean installation_running;
    pthread_t worker_thread;
} AppData;

// Global application data
static AppData *app_data = NULL;

// Progress update structure for thread communication
typedef struct {
    AppData *app_data;
    gdouble progress;
    gchar *message;
    gchar *log_message;
    StatusType log_type;
} ProgressUpdate;

// Function prototypes
static void init_app_data(AppData *data);
static gboolean set_widget_sensitive_wrapper(gpointer data);
static gboolean set_button_label_wrapper(gpointer data);
static void create_main_window(AppData *data);
static void create_header_section(GtkWidget *container);
static void create_status_section(GtkWidget *container, AppData *data);
static void create_options_section(GtkWidget *container, AppData *data);
static void create_progress_section(GtkWidget *container, AppData *data);
static void create_buttons_section(GtkWidget *container, AppData *data);
static void setup_css_styling(void);
static void on_detect_clicked(GtkWidget *widget, AppData *data);
static void on_install_clicked(GtkWidget *widget, AppData *data);
static void *detection_thread(void *arg);
static void *installation_thread(void *arg);
static gboolean detect_nvidia_gpu(SystemInfo *info);
static gboolean detect_nvidia_driver(SystemInfo *info);
static gboolean detect_cuda(SystemInfo *info);
static gboolean is_wsl_system(void);
static gboolean check_system_compatibility(AppData *data);
static gboolean check_internet_connectivity(AppData *data);
static void update_status_display(AppData *data);
static void update_status_card(GtkWidget *icon_label, GtkWidget *status_label, 
                              const gchar *icon, const gchar *text, StatusType type);
static void log_message(AppData *data, const gchar *message, StatusType type);
static gint run_command(const gchar *command, gchar **output);
static gboolean run_command_with_progress(const gchar *command, AppData *data, gdouble progress_increment);
static void show_error_dialog(GtkWidget *parent, const gchar *title, const gchar *message);
static gboolean show_confirmation_dialog(GtkWidget *parent, const gchar *title, const gchar *message);
static gchar *get_sudo_password(GtkWidget *parent);
static gboolean verify_sudo_access(const gchar *password);
static void cleanup_app_data(AppData *data);
static gboolean update_progress_ui(gpointer user_data);
static gboolean update_log_ui(gpointer user_data);
static gboolean update_status_display_wrapper(gpointer data);
static gboolean show_completion_dialog_wrapper(gpointer data);
static gboolean show_error_dialog_wrapper(gpointer data);

// CSS styling for modern appearance
static const gchar *css_style = 
"window {\n"
"    background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);\n"
"    color: #ffffff;\n"
"}\n"
".title-label {\n"
"    font-size: 24px;\n"
"    font-weight: bold;\n"
"    color: #76b900;\n"
"    margin: 20px;\n"
"}\n"
".subtitle-label {\n"
"    font-size: 12px;\n"
"    color: #a0a0a0;\n"
"    margin-bottom: 20px;\n"
"}\n"
".status-frame {\n"
"    background: rgba(255, 255, 255, 0.05);\n"
"    border-radius: 10px;\n"
"    border: 1px solid rgba(255, 255, 255, 0.1);\n"
"    margin: 10px;\n"
"    padding: 15px;\n"
"}\n"
".status-success {\n"
"    color: #28a745;\n"
"}\n"
".status-warning {\n"
"    color: #ffc107;\n"
"}\n"
".status-error {\n"
"    color: #dc3545;\n"
"}\n"
".status-info {\n"
"    color: #17a2b8;\n"
"}\n"
".console-view {\n"
"    background: #000000;\n"
"    color: #00ff00;\n"
"    font-family: monospace;\n"
"}\n";

// Main application entry point
int main(int argc, char *argv[]) {
    #ifndef __linux__
    fprintf(stderr, "This application is designed for Linux systems only.\n");
    return 1;
    #endif
    
    gtk_init(&argc, &argv);
    
    app_data = g_malloc0(sizeof(AppData));
    init_app_data(app_data);
    
    setup_css_styling();
    create_main_window(app_data);
    
    gtk_widget_show_all(app_data->main_window);
    gtk_widget_hide(app_data->progress_frame);
    
    pthread_create(&app_data->worker_thread, NULL, detection_thread, app_data);
    
    gtk_main();
    
    cleanup_app_data(app_data);
    g_free(app_data);
    
    return 0;
}

// Initialize application data structure
static void init_app_data(AppData *data) {
    data->installation_running = FALSE;
    data->system_info.gpu_detected = FALSE;
    data->system_info.driver_installed = FALSE;
    data->system_info.cuda_installed = FALSE;
    data->system_info.gpu_info = g_strdup("Unknown");
    data->system_info.driver_info = g_strdup("Unknown");
    data->system_info.cuda_info = g_strdup("Unknown");
    data->system_info.distro_codename = NULL;
}

// Create main application window
static void create_main_window(AppData *data) {
    data->main_window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(data->main_window), APP_TITLE);
    gtk_window_set_default_size(GTK_WINDOW(data->main_window), 800, 600);
    gtk_window_set_position(GTK_WINDOW(data->main_window), GTK_WIN_POS_CENTER);
    
    g_signal_connect(data->main_window, "destroy", G_CALLBACK(gtk_main_quit), NULL);
    
    GtkWidget *main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(main_box), 20);
    gtk_container_add(GTK_CONTAINER(data->main_window), main_box);
    
    create_header_section(main_box);
    create_status_section(main_box, data);
    create_options_section(main_box, data);
    create_progress_section(main_box, data);
    create_buttons_section(main_box, data);
}

// Create header section with title and subtitle
static void create_header_section(GtkWidget *container) {
    GtkWidget *header_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 5);
    gtk_box_pack_start(GTK_BOX(container), header_box, FALSE, FALSE, 0);
    
    GtkWidget *title_label = gtk_label_new("NVIDIA GPU SETUP");
    gtk_style_context_add_class(gtk_widget_get_style_context(title_label), "title-label");
    gtk_box_pack_start(GTK_BOX(header_box), title_label, FALSE, FALSE, 0);
    
    GtkWidget *subtitle_label = gtk_label_new("Automatic Driver & CUDA Installation for Live Boot Linux Systems (v" APP_VERSION ")");
    gtk_style_context_add_class(gtk_widget_get_style_context(subtitle_label), "subtitle-label");
    gtk_box_pack_start(GTK_BOX(header_box), subtitle_label, FALSE, FALSE, 0);
    
    GtkWidget *wsl_warning = gtk_label_new("⚠️ WSL users: This tool requires a live boot Linux system for GPU access");
    gtk_style_context_add_class(gtk_widget_get_style_context(wsl_warning), "subtitle-label");
    gtk_widget_set_margin_top(wsl_warning, 10);
    gtk_box_pack_start(GTK_BOX(header_box), wsl_warning, FALSE, FALSE, 0);
}

// Create status section showing system information
static void create_status_section(GtkWidget *container, AppData *data) {
    GtkWidget *status_frame = gtk_frame_new("System Status");
    gtk_style_context_add_class(gtk_widget_get_style_context(status_frame), "status-frame");
    gtk_box_pack_start(GTK_BOX(container), status_frame, FALSE, FALSE, 0);
    
    GtkWidget *status_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(status_box), 15);
    gtk_container_add(GTK_CONTAINER(status_frame), status_box);
    
    GtkWidget *gpu_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_box_pack_start(GTK_BOX(status_box), gpu_box, FALSE, FALSE, 0);
    
    data->gpu_icon_label = gtk_label_new("[DETECT]");
    gtk_label_set_markup(GTK_LABEL(data->gpu_icon_label), "<span size='large'><b>[DETECT]</b></span>");
    gtk_box_pack_start(GTK_BOX(gpu_box), data->gpu_icon_label, FALSE, FALSE, 0);
    
    GtkWidget *gpu_text_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 2);
    gtk_box_pack_start(GTK_BOX(gpu_box), gpu_text_box, TRUE, TRUE, 0);
    
    GtkWidget *gpu_title = gtk_label_new("NVIDIA GPU Detection");
    gtk_label_set_markup(GTK_LABEL(gpu_title), "<b>NVIDIA GPU Detection</b>");
    gtk_widget_set_halign(gpu_title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(gpu_text_box), gpu_title, FALSE, FALSE, 0);
    
    data->gpu_status_label = gtk_label_new("Checking for compatible GPU...");
    gtk_widget_set_halign(data->gpu_status_label, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(gpu_text_box), data->gpu_status_label, FALSE, FALSE, 0);
    
    GtkWidget *driver_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_box_pack_start(GTK_BOX(status_box), driver_box, FALSE, FALSE, 0);
    
    data->driver_icon_label = gtk_label_new("[DRIVER]");
    gtk_label_set_markup(GTK_LABEL(data->driver_icon_label), "<span size='large'><b>[DRIVER]</b></span>");
    gtk_box_pack_start(GTK_BOX(driver_box), data->driver_icon_label, FALSE, FALSE, 0);
    
    GtkWidget *driver_text_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 2);
    gtk_box_pack_start(GTK_BOX(driver_box), driver_text_box, TRUE, TRUE, 0);
    
    GtkWidget *driver_title = gtk_label_new("Driver Status");
    gtk_label_set_markup(GTK_LABEL(driver_title), "<b>Driver Status</b>");
    gtk_widget_set_halign(driver_title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(driver_text_box), driver_title, FALSE, FALSE, 0);
    
    data->driver_status_label = gtk_label_new("Checking current installation...");
    gtk_widget_set_halign(data->driver_status_label, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(driver_text_box), data->driver_status_label, FALSE, FALSE, 0);
    
    GtkWidget *cuda_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_box_pack_start(GTK_BOX(status_box), cuda_box, FALSE, FALSE, 0);
    
    data->cuda_icon_label = gtk_label_new("[CUDA]");
    gtk_label_set_markup(GTK_LABEL(data->cuda_icon_label), "<span size='large'><b>[CUDA]</b></span>");
    gtk_box_pack_start(GTK_BOX(cuda_box), data->cuda_icon_label, FALSE, FALSE, 0);
    
    GtkWidget *cuda_text_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 2);
    gtk_box_pack_start(GTK_BOX(cuda_box), cuda_text_box, TRUE, TRUE, 0);
    
    GtkWidget *cuda_title = gtk_label_new("CUDA Status");
    gtk_label_set_markup(GTK_LABEL(cuda_title), "<b>CUDA Status</b>");
    gtk_widget_set_halign(cuda_title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(cuda_text_box), cuda_title, FALSE, FALSE, 0);
    
    data->cuda_status_label = gtk_label_new("Checking CUDA availability...");
    gtk_widget_set_halign(data->cuda_status_label, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(cuda_text_box), data->cuda_status_label, FALSE, FALSE, 0);
}

// Create installation options section
static void create_options_section(GtkWidget *container, AppData *data) {
    GtkWidget *options_frame = gtk_frame_new("Installation Options");
    gtk_style_context_add_class(gtk_widget_get_style_context(options_frame), "status-frame");
    gtk_box_pack_start(GTK_BOX(container), options_frame, FALSE, FALSE, 0);
    
    GtkWidget *options_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(options_box), 15);
    gtk_container_add(GTK_CONTAINER(options_frame), options_box);
    
    data->install_driver_check = gtk_check_button_new_with_label("Install NVIDIA Driver (Latest Proprietary)");
    gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(data->install_driver_check), TRUE);
    gtk_box_pack_start(GTK_BOX(options_box), data->install_driver_check, FALSE, FALSE, 0);
    
    GtkWidget *driver_desc = gtk_label_new("    • Installs latest NVIDIA proprietary driver for optimal performance");
    gtk_widget_set_halign(driver_desc, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(options_box), driver_desc, FALSE, FALSE, 0);
    
    data->install_cuda_check = gtk_check_button_new_with_label("Install CUDA Toolkit (Latest Stable)");
    gtk_box_pack_start(GTK_BOX(options_box), data->install_cuda_check, FALSE, FALSE, 0);
    
    GtkWidget *cuda_desc = gtk_label_new("    • Installs CUDA for GPU computing and sets up environment variables");
    gtk_widget_set_halign(cuda_desc, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(options_box), cuda_desc, FALSE, FALSE, 0);
}

// Create progress section for installation tracking
static void create_progress_section(GtkWidget *container, AppData *data) {
    data->progress_frame = gtk_frame_new("Installation Progress");
    gtk_style_context_add_class(gtk_widget_get_style_context(data->progress_frame), "status-frame");
    gtk_box_pack_start(GTK_BOX(container), data->progress_frame, TRUE, TRUE, 0);
    
    GtkWidget *progress_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(progress_box), 15);
    gtk_container_add(GTK_CONTAINER(data->progress_frame), progress_box);
    
    data->progress_bar = gtk_progress_bar_new();
    gtk_progress_bar_set_show_text(GTK_PROGRESS_BAR(data->progress_bar), TRUE);
    gtk_box_pack_start(GTK_BOX(progress_box), data->progress_bar, FALSE, FALSE, 0);
    
    data->progress_label = gtk_label_new("Ready to start...");
    gtk_widget_set_halign(data->progress_label, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(progress_box), data->progress_label, FALSE, FALSE, 0);
    
    GtkWidget *console_scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(console_scroll), 
                                   GTK_POLICY_AUTOMATIC, GTK_POLICY_AUTOMATIC);
    gtk_widget_set_size_request(console_scroll, -1, 200);
    gtk_box_pack_start(GTK_BOX(progress_box), console_scroll, TRUE, TRUE, 0);
    
    data->console_textview = gtk_text_view_new();
    data->console_buffer = gtk_text_view_get_buffer(GTK_TEXT_VIEW(data->console_textview));
    gtk_text_buffer_set_text(data->console_buffer, "", -1); // Initialize empty
    gtk_text_view_set_editable(GTK_TEXT_VIEW(data->console_textview), FALSE);
    gtk_text_view_set_cursor_visible(GTK_TEXT_VIEW(data->console_textview), FALSE);
    gtk_style_context_add_class(gtk_widget_get_style_context(data->console_textview), "console-view");
    gtk_container_add(GTK_CONTAINER(console_scroll), data->console_textview);
}

// Create buttons section
static void create_buttons_section(GtkWidget *container, AppData *data) {
    GtkWidget *button_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_widget_set_halign(button_box, GTK_ALIGN_CENTER);
    gtk_box_pack_start(GTK_BOX(container), button_box, FALSE, FALSE, 0);
    
    data->detect_button = gtk_button_new_with_label("[DETECT] System");
    gtk_widget_set_size_request(data->detect_button, 150, 40);
    g_signal_connect(data->detect_button, "clicked", G_CALLBACK(on_detect_clicked), data);
    gtk_box_pack_start(GTK_BOX(button_box), data->detect_button, FALSE, FALSE, 0);
    
    data->install_button = gtk_button_new_with_label("[INSTALL] Start");
    gtk_widget_set_size_request(data->install_button, 180, 40);
    g_signal_connect(data->install_button, "clicked", G_CALLBACK(on_install_clicked), data);
    gtk_box_pack_start(GTK_BOX(button_box), data->install_button, FALSE, FALSE, 0);
    
    GtkWidget *close_button = gtk_button_new_with_label("[CLOSE]");
    gtk_widget_set_size_request(close_button, 120, 40);
    g_signal_connect(close_button, "clicked", G_CALLBACK(gtk_main_quit), NULL);
    gtk_box_pack_start(GTK_BOX(button_box), close_button, FALSE, FALSE, 0);
}

// Setup CSS styling
static void setup_css_styling(void) {
    GtkCssProvider *css_provider = gtk_css_provider_new();
    GError *error = NULL;
    
    gtk_css_provider_load_from_data(css_provider, css_style, -1, &error);
    
    if (error != NULL) {
        g_warning("Failed to load CSS: %s", error->message);
        g_error_free(error);
    } else {
        gtk_style_context_add_provider_for_screen(
            gdk_screen_get_default(),
            GTK_STYLE_PROVIDER(css_provider),
            GTK_STYLE_PROVIDER_PRIORITY_APPLICATION
        );
    }
    
    g_object_unref(css_provider);
}

// Handle detect button click
static void on_detect_clicked(GtkWidget *widget __attribute__((unused)), AppData *data) {
    if (data->installation_running) {
        return;
    }
    
    gtk_widget_set_sensitive(data->detect_button, FALSE);
    log_message(data, "Running system detection...", STATUS_INFO);
    
    pthread_create(&data->worker_thread, NULL, detection_thread, data);
}

// Handle install button click
static void on_install_clicked(GtkWidget *widget __attribute__((unused)), AppData *data) {
    if (data->installation_running) {
        return;
    }
    
    if (is_wsl_system()) {
        show_error_dialog(data->main_window, "WSL Environment Detected", 
                         "This tool cannot install NVIDIA drivers in WSL.\n\n"
                         "This tool is designed for live boot Linux systems.\n\n"
                         "To use this tool:\n"
                         "1. Create a live USB with Ubuntu/Debian\n"
                         "2. Boot from the USB on the target system\n"
                         "3. Run this tool on the live system");
        return;
    }
    
    if (!data->system_info.gpu_detected) {
        show_error_dialog(data->main_window, "Error", 
                         "No NVIDIA GPU detected. Installation cannot proceed.");
        return;
    }
    
    gboolean install_driver = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(data->install_driver_check));
    gboolean install_cuda = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(data->install_cuda_check));
    
    if (!install_driver && !install_cuda) {
        show_error_dialog(data->main_window, "Warning", 
                         "Please select at least one installation option.");
        return;
    }
    
    GString *message = g_string_new("This will install:\n\n");
    if (install_driver) {
        g_string_append(message, "• NVIDIA Driver\n");
    }
    if (install_cuda) {
        g_string_append(message, "• CUDA Toolkit\n");
    }
    g_string_append(message, "\nThe installation may take several minutes and require a reboot.\nContinue?");
    
    if (!show_confirmation_dialog(data->main_window, "Confirm Installation", message->str)) {
        g_string_free(message, TRUE);
        return;
    }
    
    g_string_free(message, TRUE);
    
    gchar *password = get_sudo_password(data->main_window);
    if (password == NULL) {
        return;
    }
    
    if (!verify_sudo_access(password)) {
        show_error_dialog(data->main_window, "Error", 
                         "Invalid password or insufficient privileges.");
        g_free(password);
        return;
    }
    
    g_free(password);
    
    data->installation_running = TRUE;
    gtk_widget_show(data->progress_frame);
    gtk_widget_set_sensitive(data->install_button, FALSE);
    gtk_widget_set_sensitive(data->detect_button, FALSE);
    gtk_button_set_label(GTK_BUTTON(data->install_button), "Installing...");
    
    log_message(data, "Starting installation process...", STATUS_INFO);
    
    pthread_create(&data->worker_thread, NULL, installation_thread, data);
}

// Detection thread function
static void *detection_thread(void *arg) {
    AppData *data = (AppData *)arg;
    
    log_message(data, "Detecting system components...", STATUS_INFO);
    
    // Detect distro
    log_message(data, "Detecting Linux distribution...", STATUS_INFO);
    run_command("lsb_release -cs 2>/dev/null", &data->system_info.distro_codename);
    if (data->system_info.distro_codename) {
        g_strchomp(data->system_info.distro_codename);
        log_message(data, g_strdup_printf("Distribution codename: %s", data->system_info.distro_codename), STATUS_INFO);
    } else {
        data->system_info.distro_codename = g_strdup("unknown");
        log_message(data, "Unable to detect distribution codename", STATUS_WARNING);
    }
    
    struct timespec delay = {0, DETECTION_DELAY_NS};
    nanosleep(&delay, NULL);
    
    log_message(data, "Checking for NVIDIA GPU...", STATUS_INFO);
    detect_nvidia_gpu(&data->system_info);
    
    nanosleep(&delay, NULL);
    
    log_message(data, "Checking driver status...", STATUS_INFO);
    detect_nvidia_driver(&data->system_info);
    
    nanosleep(&delay, NULL);
    
    log_message(data, "Checking CUDA status...", STATUS_INFO);
    detect_cuda(&data->system_info);
    
    ProgressUpdate *update = g_malloc(sizeof(ProgressUpdate));
    update->app_data = data;
    update->progress = 0.0;
    update->message = NULL;
    update->log_message = g_strdup("System detection completed.");
    update->log_type = STATUS_INFO;
    g_idle_add(update_progress_ui, update);
    
    g_idle_add(update_status_display_wrapper, data);
    
    g_idle_add(set_widget_sensitive_wrapper, data->detect_button);
    
    return NULL;
}

// Installation thread function
static void *installation_thread(void *arg) {
    AppData *data = (AppData *)arg;
    
    gboolean install_driver = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(data->install_driver_check));
    gboolean install_cuda = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(data->install_cuda_check));
    
    gboolean success = TRUE;
    gdouble progress = 0.0;
    gint total_steps = 1 + (install_driver ? 4 : 0) + (install_cuda ? 4 : 0); // Update, prereqs, + steps per option
    gdouble progress_increment = 100.0 / total_steps;
    
    if (!check_system_compatibility(data)) {
        data->installation_running = FALSE;
        g_idle_add(set_widget_sensitive_wrapper, data->install_button);
        g_idle_add(set_widget_sensitive_wrapper, data->detect_button);
        g_idle_add(set_button_label_wrapper, data->install_button);
        return NULL;
    }
    
    if (!check_internet_connectivity(data)) {
        data->installation_running = FALSE;
        g_idle_add(set_widget_sensitive_wrapper, data->install_button);
        g_idle_add(set_widget_sensitive_wrapper, data->detect_button);
        g_idle_add(set_button_label_wrapper, data->install_button);
        g_idle_add(show_error_dialog_wrapper, data);
        return NULL;
    }
    
    // Update package lists
    progress += progress_increment;
    ProgressUpdate *update = g_malloc(sizeof(ProgressUpdate));
    update->app_data = data;
    update->progress = progress;
    update->message = g_strdup("Updating package lists...");
    update->log_message = g_strdup("Updating package repositories...");
    update->log_type = STATUS_INFO;
    g_idle_add(update_progress_ui, update);
    
    if (!run_command_with_progress("sudo apt-get update", data, progress_increment)) {
        success = FALSE;
        goto cleanup_install;
    }
    
    // Install prerequisites
    progress += progress_increment;
    update = g_malloc(sizeof(ProgressUpdate));
    update->app_data = data;
    update->progress = progress;
    update->message = g_strdup("Installing prerequisites...");
    update->log_message = g_strdup("Installing required packages...");
    update->log_type = STATUS_INFO;
    g_idle_add(update_progress_ui, update);
    
    const gchar *prereq_cmd = "sudo apt-get install -y software-properties-common "
                             "apt-transport-https ca-certificates curl wget gnupg "
                             "lsb-release build-essential dkms";
    
    if (!run_command_with_progress(prereq_cmd, data, progress_increment)) {
        success = FALSE;
        goto cleanup_install;
    }
    
    if (install_driver) {
        // Add NVIDIA repository
        progress += progress_increment;
        update = g_malloc(sizeof(ProgressUpdate));
        update->app_data = data;
        update->progress = progress;
        update->message = g_strdup("Adding NVIDIA repository...");
        update->log_message = g_strdup("Adding NVIDIA repository...");
        update->log_type = STATUS_INFO;
        g_idle_add(update_progress_ui, update);
        
        gchar *repo_cmd = g_strdup_printf(
            "wget https://developer.download.nvidia.com/compute/cuda/repos/%s/x86_64/cuda-keyring_1.1-1_all.deb",
            data->system_info.distro_codename);
        if (!run_command_with_progress(repo_cmd, data, progress_increment)) {
            success = FALSE;
            g_free(repo_cmd);
            goto cleanup_install;
        }
        g_free(repo_cmd);
        
        if (!run_command_with_progress("sudo dpkg -i cuda-keyring_1.1-1_all.deb", data, progress_increment)) {
            success = FALSE;
            goto cleanup_install;
        }
        
        // Update package lists after adding repository
        progress += progress_increment;
        update = g_malloc(sizeof(ProgressUpdate));
        update->app_data = data;
        update->progress = progress;
        update->message = g_strdup("Updating package lists...");
        update->log_message = g_strdup("Updating package lists with NVIDIA repository...");
        update->log_type = STATUS_INFO;
        g_idle_add(update_progress_ui, update);
        
        if (!run_command_with_progress("sudo apt-get update", data, progress_increment)) {
            success = FALSE;
            goto cleanup_install;
        }
        
        // Install NVIDIA driver
        progress += progress_increment;
        update = g_malloc(sizeof(ProgressUpdate));
        update->app_data = data;
        update->progress = progress;
        update->message = g_strdup("Installing NVIDIA driver...");
        update->log_message = g_strdup("Installing NVIDIA proprietary driver...");
        update->log_type = STATUS_INFO;
        g_idle_add(update_progress_ui, update);
        
        if (!run_command_with_progress("sudo apt-get install -y cuda-drivers", data, progress_increment)) {
            success = FALSE;
            goto cleanup_install;
        }
    }
    
    if (install_cuda) {
        // Add CUDA repository (already added with driver, but ensure keyring)
        progress += progress_increment;
        update = g_malloc(sizeof(ProgressUpdate));
        update->app_data = data;
        update->progress = progress;
        update->message = g_strdup("Verifying CUDA repository...");
        update->log_message = g_strdup("Ensuring NVIDIA CUDA repository...");
        update->log_type = STATUS_INFO;
        g_idle_add(update_progress_ui, update);
        
        if (!run_command_with_progress("sudo apt-get update", data, progress_increment)) {
            success = FALSE;
            goto cleanup_install;
        }
        
        // Install CUDA toolkit
        progress += progress_increment;
        update = g_malloc(sizeof(ProgressUpdate));
        update->app_data = data;
        update->progress = progress;
        update->message = g_strdup("Installing CUDA toolkit...");
        update->log_message = g_strdup("Installing CUDA toolkit...");
        update->log_type = STATUS_INFO;
        g_idle_add(update_progress_ui, update);
        
        if (!run_command_with_progress("sudo apt-get install -y cuda-toolkit-12-6", data, progress_increment)) {
            success = FALSE;
            goto cleanup_install;
        }
        
        // Setup environment variables
        progress += progress_increment;
        update = g_malloc(sizeof(ProgressUpdate));
        update->app_data = data;
        update->progress = progress;
        update->message = g_strdup("Setting up environment variables...");
        update->log_message = g_strdup("Configuring CUDA environment...");
        update->log_type = STATUS_INFO;
        g_idle_add(update_progress_ui, update);
        
        const gchar *env_cmd = "echo 'export PATH=/usr/local/cuda/bin${PATH:+:$PATH}' | sudo tee /etc/profile.d/cuda.sh && "
                              "echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}' | sudo tee -a /etc/profile.d/cuda.sh";
        
        if (!run_command_with_progress(env_cmd, data, progress_increment)) {
            success = FALSE;
            goto cleanup_install;
        }
    }
    
    // Final update
    progress = 100.0;
    update = g_malloc(sizeof(ProgressUpdate));
    update->app_data = data;
    update->progress = progress;
    update->message = g_strdup("Installation completed successfully!");
    update->log_message = g_strdup("Installation completed successfully!");
    update->log_type = STATUS_SUCCESS;
    g_idle_add(update_progress_ui, update);
    
    // Clean up downloaded files
    run_command("rm -f cuda-keyring_1.1-1_all.deb", NULL);
    
cleanup_install:
    if (!success) {
        run_command("sudo apt-get autoremove -y", NULL); // Clean up partial installs
    }
    
    data->installation_running = FALSE;
    
    g_idle_add(set_widget_sensitive_wrapper, data->install_button);
    g_idle_add(set_widget_sensitive_wrapper, data->detect_button);
    g_idle_add(set_button_label_wrapper, data->install_button);
    
    if (success) {
        g_idle_add(show_completion_dialog_wrapper, data);
    } else {
        g_idle_add(show_error_dialog_wrapper, data);
    }
    
    return NULL;
}

// Detect NVIDIA GPU using lspci
static gboolean detect_nvidia_gpu(SystemInfo *info) {
    gchar *output = NULL;
    gint result = run_command("lspci | grep -i nvidia", &output);
    
    if (result == 0 && output != NULL && strlen(output) > 0) {
        info->gpu_detected = TRUE;
        g_strchug(output);
        g_strchomp(output);
        info->gpu_info = g_strdup_printf("Detected: %s", output);
        g_free(output);
        return TRUE;
    }
    
    info->gpu_detected = FALSE;
    info->gpu_info = g_strdup("No NVIDIA GPU detected");
    if (output) g_free(output);
    return FALSE;
}

// Detect NVIDIA driver installation
static gboolean detect_nvidia_driver(SystemInfo *info) {
    gchar *output = NULL;
    gint result = run_command("nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits 2>/dev/null", &output);
    
    if (result == 0 && output != NULL && strlen(output) > 0) {
        info->driver_installed = TRUE;
        g_strchug(output);
        g_strchomp(output);
        info->driver_info = g_strdup_printf("Installed: Version %s", output);
        g_free(output);
        return TRUE;
    }
    
    info->driver_installed = FALSE;
    info->driver_info = g_strdup("Not installed");
    if (output) g_free(output);
    return FALSE;
}

// Detect CUDA installation
static gboolean detect_cuda(SystemInfo *info) {
    gchar *output = NULL;
    gint result = run_command("nvcc --version 2>/dev/null | grep 'release' | awk '{print $6}' | cut -c2-", &output);
    
    if (result == 0 && output != NULL && strlen(output) > 0) {
        info->cuda_installed = TRUE;
        g_strchug(output);
        g_strchomp(output);
        info->cuda_info = g_strdup_printf("Installed: CUDA %s", output);
        g_free(output);
        return TRUE;
    }
    
    info->cuda_installed = FALSE;
    info->cuda_info = g_strdup("Not installed");
    if (output) g_free(output);
    return FALSE;
}

// Check if running in WSL
static gboolean is_wsl_system(void) {
    gchar *output = NULL;
    gint result = run_command("cat /proc/version 2>/dev/null | grep -i microsoft", &output);
    
    gboolean is_wsl = (result == 0 && output != NULL && strlen(output) > 0);
    if (output) g_free(output);
    return is_wsl;
}

// Check internet connectivity
static gboolean check_internet_connectivity(AppData *data) {
    gint result = run_command("ping -c 1 8.8.8.8 >/dev/null 2>&1", NULL);
    if (result != 0) {
        log_message(data, "No internet connection detected. Installation requires internet access.", STATUS_ERROR);
        return FALSE;
    }
    return TRUE;
}

// Check system compatibility before installation
static gboolean check_system_compatibility(AppData *data) {
    if (is_wsl_system()) {
        log_message(data, "ERROR: Running in WSL. NVIDIA driver installation requires native Linux.", STATUS_ERROR);
        log_message(data, "This tool is designed for live boot Linux systems or native installations.", STATUS_INFO);
        log_message(data, "To use this tool:", STATUS_INFO);
        log_message(data, "1. Create a live USB with Ubuntu/Debian", STATUS_INFO);
        log_message(data, "2. Boot from the USB on the target system", STATUS_INFO);
        log_message(data, "3. Run this tool on the live system", STATUS_INFO);
        return FALSE;
    }
    
    if (getuid() == 0) {
        log_message(data, "WARNING: Running as root. This is not recommended for security reasons.", STATUS_WARNING);
    }
    
    gchar *output = NULL;
    gint result = run_command("df / | tail -1 | awk '{print $4}'", &output);
    if (result == 0 && output != NULL) {
        gint64 free_space = g_ascii_strtoll(output, NULL, 10);
        if (free_space < 2000000) { // Less than 2GB free
            log_message(data, "WARNING: Low disk space detected. Installation may fail.", STATUS_WARNING);
        }
    }
    if (output) g_free(output);
    
    // Check Secure Boot
    result = run_command("mokutil --sb-state 2>/dev/null", &output);
    if (result == 0 && output != NULL && strstr(output, "enabled")) {
        log_message(data, "WARNING: Secure Boot is enabled. Driver installation may require additional steps.", STATUS_WARNING);
    }
    if (output) g_free(output);
    
    // Check distro compatibility
    if (data->system_info.distro_codename) {
        if (g_strcmp0(data->system_info.distro_codename, "bullseye") == 0) {
            log_message(data, "WARNING: Debian 11 is EOL. Upgrade recommended.", STATUS_WARNING);
        } else if (g_strcmp0(data->system_info.distro_codename, "bookworm") != 0 &&
                   g_strcmp0(data->system_info.distro_codename, "jammy") != 0 &&
                   g_strcmp0(data->system_info.distro_codename, "noble") != 0) {
            log_message(data, "WARNING: Unsupported distro. Installation may fail.", STATUS_WARNING);
        }
    }
    
    return TRUE;
}

// Update status display with current system information
static void update_status_display(AppData *data) {
    update_status_card(data->gpu_icon_label, data->gpu_status_label,
                      data->system_info.gpu_detected ? "[OK]" : "[FAIL]",
                      data->system_info.gpu_info,
                      data->system_info.gpu_detected ? STATUS_SUCCESS : STATUS_ERROR);
    
    update_status_card(data->driver_icon_label, data->driver_status_label,
                      data->system_info.driver_installed ? "[OK]" : "[WARN]",
                      data->system_info.driver_info,
                      data->system_info.driver_installed ? STATUS_SUCCESS : STATUS_WARNING);
    
    update_status_card(data->cuda_icon_label, data->cuda_status_label,
                      data->system_info.cuda_installed ? "[OK]" : "[INFO]",
                      data->system_info.cuda_info,
                      data->system_info.cuda_installed ? STATUS_SUCCESS : STATUS_INFO);
}

// Update individual status card
static void update_status_card(GtkWidget *icon_label, GtkWidget *status_label,
                              const gchar *icon, const gchar *text, StatusType type) {
    gchar *icon_markup = g_strdup_printf("<span size='large'>%s</span>", icon);
    gtk_label_set_markup(GTK_LABEL(icon_label), icon_markup);
    g_free(icon_markup);
    
    gtk_label_set_text(GTK_LABEL(status_label), text);
    
    GtkStyleContext *context = gtk_widget_get_style_context(status_label);
    gtk_style_context_remove_class(context, "status-success");
    gtk_style_context_remove_class(context, "status-warning");
    gtk_style_context_remove_class(context, "status-error");
    gtk_style_context_remove_class(context, "status-info");
    
    switch (type) {
        case STATUS_SUCCESS:
            gtk_style_context_add_class(context, "status-success");
            break;
        case STATUS_WARNING:
            gtk_style_context_add_class(context, "status-warning");
            break;
        case STATUS_ERROR:
            gtk_style_context_add_class(context, "status-error");
            break;
        case STATUS_INFO:
            gtk_style_context_add_class(context, "status-info");
            break;
        default:
            break;
    }
}

// Log message to console with line limit
static void log_message(AppData *data, const gchar *message, StatusType type) {
    if (!data || !data->console_buffer) return;
    
    GtkTextIter iter;
    gtk_text_buffer_get_end_iter(data->console_buffer, &iter);
    
    GDateTime *now = g_date_time_new_now_local();
    gchar *timestamp = g_date_time_format(now, "%H:%M:%S");
    
    const gchar *status_icon = "";
    switch (type) {
        case STATUS_SUCCESS: status_icon = "[OK]"; break;
        case STATUS_WARNING: status_icon = "[WARN]"; break;
        case STATUS_ERROR: status_icon = "[ERROR]"; break;
        case STATUS_INFO: status_icon = "[INFO]"; break;
        default: status_icon = "[*]"; break;
    }
    
    gchar *formatted_message = g_strdup_printf("[%s] %s %s\n", timestamp, status_icon, message);
    
    // Check line count and trim if necessary
    gint line_count = gtk_text_buffer_get_line_count(data->console_buffer);
    if (line_count >= MAX_LOG_LINES) {
        GtkTextIter start, end;
        gtk_text_buffer_get_iter_at_line(data->console_buffer, &start, 0);
        gtk_text_buffer_get_iter_at_line(data->console_buffer, &end, line_count - MAX_LOG_LINES + 1);
        gtk_text_buffer_delete(data->console_buffer, &start, &end);
        gtk_text_buffer_get_end_iter(data->console_buffer, &iter);
    }
    
    gtk_text_buffer_insert(data->console_buffer, &iter, formatted_message, -1);
    
    gtk_text_view_scroll_to_iter(GTK_TEXT_VIEW(data->console_textview), &iter, 0.0, FALSE, 0.0, 0.0);
    
    g_free(formatted_message);
    g_free(timestamp);
    g_date_time_unref(now);
}

// Run command and capture output
static gint run_command(const gchar *command, gchar **output) {
    FILE *pipe = popen(command, "r");
    if (!pipe) return -1;
    
    GString *result = g_string_new("");
    gchar buffer[256];
    
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        g_string_append(result, buffer);
    }
    
    gint status = pclose(pipe);
    
    if (output) {
        *output = g_string_free(result, FALSE);
    } else {
        g_string_free(result, TRUE);
    }
    
    return status;
}

// Run command with progress updates
static gboolean run_command_with_progress(const gchar *command, AppData *data, gdouble progress_increment) {
    ProgressUpdate *update = g_malloc(sizeof(ProgressUpdate));
    update->app_data = data;
    update->progress = 0.0;
    update->message = NULL;
    update->log_message = g_strdup_printf("Running: %s", command);
    update->log_type = STATUS_INFO;
    g_idle_add(update_progress_ui, update);
    
    gint result = run_command(command, NULL);
    
    if (result == 0) {
        update = g_malloc(sizeof(ProgressUpdate));
        update->app_data = data;
        update->progress = progress_increment;
        update->message = NULL;
        update->log_message = g_strdup("Command completed successfully");
        update->log_type = STATUS_SUCCESS;
        g_idle_add(update_progress_ui, update);
        return TRUE;
    } else {
        update = g_malloc(sizeof(ProgressUpdate));
        update->app_data = data;
        update->progress = 0.0;
        update->message = NULL;
        update->log_message = g_strdup_printf("Command failed with exit code %d", result);
        update->log_type = STATUS_ERROR;
        g_idle_add(update_progress_ui, update);
        return FALSE;
    }
}

// Show error dialog
static void show_error_dialog(GtkWidget *parent, const gchar *title, const gchar *message) {
    GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(parent),
                                              GTK_DIALOG_MODAL,
                                              GTK_MESSAGE_ERROR,
                                              GTK_BUTTONS_OK,
                                              "%s", title);
    
    gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog), "%s", message);
    gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);
}

// Show confirmation dialog
static gboolean show_confirmation_dialog(GtkWidget *parent, const gchar *title, const gchar *message) {
    GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(parent),
                                              GTK_DIALOG_MODAL,
                                              GTK_MESSAGE_QUESTION,
                                              GTK_BUTTONS_YES_NO,
                                              "%s", title);
    
    gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog), "%s", message);
    gint response = gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);
    
    return (response == GTK_RESPONSE_YES);
}

// Get sudo password from user
static gchar *get_sudo_password(GtkWidget *parent) {
    GtkWidget *dialog = gtk_dialog_new_with_buttons("Authentication Required",
                                                   GTK_WINDOW(parent),
                                                   GTK_DIALOG_MODAL,
                                                   "OK", GTK_RESPONSE_OK,
                                                   "Cancel", GTK_RESPONSE_CANCEL,
                                                   NULL);
    
    gtk_window_set_default_size(GTK_WINDOW(dialog), 400, 150);
    
    GtkWidget *content_area = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    gtk_container_set_border_width(GTK_CONTAINER(content_area), 20);
    
    GtkWidget *label = gtk_label_new("This operation requires administrator privileges.\nPlease enter your password:");
    gtk_box_pack_start(GTK_BOX(content_area), label, FALSE, FALSE, 10);
    
    GtkWidget *entry = gtk_entry_new();
    gtk_entry_set_visibility(GTK_ENTRY(entry), FALSE);
    gtk_entry_set_activates_default(GTK_ENTRY(entry), TRUE);
    gtk_box_pack_start(GTK_BOX(content_area), entry, FALSE, FALSE, 10);
    
    gtk_widget_show_all(dialog);
    gtk_widget_grab_focus(entry);
    
    gint response = gtk_dialog_run(GTK_DIALOG(dialog));
    gchar *password = NULL;
    
    if (response == GTK_RESPONSE_OK) {
        password = g_strdup(gtk_entry_get_text(GTK_ENTRY(entry)));
    }
    
    gtk_widget_destroy(dialog);
    return password;
}

// Verify sudo access with password
static gboolean verify_sudo_access(const gchar *password) {
    if (!password) return FALSE;
    
    FILE *pipe = popen("sudo -S echo 'test' >/dev/null 2>&1", "w");
    if (!pipe) return FALSE;
    
    fputs(password, pipe);
    fputs("\n", pipe);
    fflush(pipe);
    
    gint status = pclose(pipe);
    return (status == 0);
}

// Clean up application data
static void cleanup_app_data(AppData *data) {
    if (!data) return;
    
    if (data->system_info.gpu_info) g_free(data->system_info.gpu_info);
    if (data->system_info.driver_info) g_free(data->system_info.driver_info);
    if (data->system_info.cuda_info) g_free(data->system_info.cuda_info);
    if (data->system_info.distro_codename) g_free(data->system_info.distro_codename);
    
    if (data->worker_thread) {
        pthread_join(data->worker_thread, NULL);
    }
}

// Update progress UI from main thread
static gboolean update_progress_ui(gpointer user_data) {
    ProgressUpdate *update = (ProgressUpdate *)user_data;
    if (!update || !update->app_data) return FALSE;
    
    AppData *data = update->app_data;
    
    if (update->message) {
        gtk_progress_bar_set_fraction(GTK_PROGRESS_BAR(data->progress_bar), update->progress / 100.0);
        gtk_progress_bar_set_text(GTK_PROGRESS_BAR(data->progress_bar), update->message);
        gtk_label_set_text(GTK_LABEL(data->progress_label), update->message);
    }
    
    if (update->log_message) {
        log_message(data, update->log_message, update->log_type);
    }
    
    if (update->message) g_free(update->message);
    if (update->log_message) g_free(update->log_message);
    g_free(update);
    
    return FALSE;
}

// Update log UI from main thread
static gboolean update_log_ui(gpointer user_data) {
    gchar *log_data = (gchar *)user_data;
    if (!log_data || !app_data) return FALSE;
    
    gchar **parts = g_strsplit(log_data, "|", 2);
    if (g_strv_length(parts) == 2) {
        StatusType type = STATUS_INFO;
        if (strcmp(parts[0], "SUCCESS") == 0) type = STATUS_SUCCESS;
        else if (strcmp(parts[0], "WARNING") == 0) type = STATUS_WARNING;
        else if (strcmp(parts[0], "ERROR") == 0) type = STATUS_ERROR;
        else if (strcmp(parts[0], "INFO") == 0) type = STATUS_INFO;
        
        log_message(app_data, parts[1], type);
    }
    
    g_strfreev(parts);
    g_free(log_data);
    return FALSE;
}

// Wrapper functions for g_idle_add
static gboolean set_widget_sensitive_wrapper(gpointer data) {
    GtkWidget *widget = (GtkWidget *)data;
    gtk_widget_set_sensitive(widget, TRUE);
    return FALSE;
}

static gboolean update_status_display_wrapper(gpointer data) {
    AppData *app_data = (AppData *)data;
    update_status_display(app_data);
    return FALSE;
}

static gboolean set_button_label_wrapper(gpointer data) {
    GtkButton *button = (GtkButton *)data;
    gtk_button_set_label(button, "[INSTALL] Start");
    return FALSE;
}

static gboolean show_completion_dialog_wrapper(gpointer data) {
    AppData *app_data = (AppData *)data;
    show_confirmation_dialog(app_data->main_window, "Installation Complete", 
                            "Installation completed successfully!\n\n"
                            "Please reboot your system to load the drivers.\n\n"
                            "After reboot, verify with:\n"
                            "• nvidia-smi (for driver)\n"
                            "• nvcc --version (for CUDA)\n\n"
                            "Would you like to reboot now?");
    return FALSE;
}

static gboolean show_error_dialog_wrapper(gpointer data) {
    AppData *app_data = (AppData *)data;
    show_error_dialog(app_data->main_window, "Installation Failed", 
                     "Installation failed. Please check the console output for details.\n\n"
                     "Ensure you have internet access and sufficient disk space.");
    return FALSE;
}