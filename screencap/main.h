uint32_t screen = 0;
#define DISPMANX_DISPLAY_HANDLE_T display = vc_dispmanx_display_open(screen);
DISPMANX_MODEINFO_T info;
int ret = vc_dispmanx_display_get_info(display, &info);

/* DispmanX expects buffer rows to be aligned to a 32 bit boundary */
int pitch = ALIGN_UP(2 * info.width, 32);
uint32_t vc_image_ptr;
VC_IMAGE_TYPE_T type = VC_IMAGE_RGB565;
    DISPMANX_RESOURCE_HANDLE_T resource = vc_dispmanx_resource_create(
        type, info.width, info.height, &vc_image_ptr
    );
    
VC_RECT_T rect;
vc_dispmanx_rect_set(&rect, 0, 0, info.width, info.height);