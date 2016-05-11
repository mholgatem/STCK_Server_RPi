// A simple demo using dispmanx to display get screenshot

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <assert.h>
#include <unistd.h>
#include <sys/time.h>

#include "bcm_host.h"
#include "Python.h"
#include "jpeglib.h"


#ifndef ALIGN_UP
#define ALIGN_UP(x,y)  ((x + (y)-1) & ~((y)-1))
#endif

#define C565_r(x) (((x) & 0xF800) >> 11)
#define C565_g(x) (((x) & 0x07E0) >> 5)
#define C565_b(x)  ((x) & 0x001F)

#define C565_red(x)   ( (C565_r(x) << 3 | C565_r(x) >> 2))
#define C565_green(x) ( (C565_g(x) << 2 | C565_g(x) >> 4))
#define C565_blue(x)  ( (C565_b(x) << 3 | C565_b(x) >> 2))


uint32_t screen = 0;
DISPMANX_DISPLAY_HANDLE_T display = 0;
DISPMANX_MODEINFO_T info;
int ret;
typedef enum { false, true } bool;
bool initialized = false;

/* DispmanX expects buffer rows to be aligned to a 32 bit boundary */
int pitch = 0;
int quality = 75;
float rate = 0.1f;
int raw = 0;
struct timeval lastStreamImage, currentTime;

uint32_t vc_image_ptr;
VC_IMAGE_TYPE_T type;
DISPMANX_RESOURCE_HANDLE_T resource;
VC_RECT_T rect;
unsigned char *image = '\0';
unsigned char *buffer = '\0';


/*
INIT
-----
Arguments:
quality - quality of the jpeg compression (10 to 100)
width - width of the output image
height - height of the output image
rate - delay between frames
raw_format - return RGB565 (.ppm) format instead of JPG
*/
static PyObject *
_streamInit(PyObject *self, PyObject *args, PyObject *kwargs) 
{
    int tempQuality = 75;
    int width = -1;
    int height = -1;
    
     static char *kwlist[] = {
        "quality",
        "width",
        "height",
        "rate",
        "raw_format",
        NULL
    };
    
    // parse arguments
    PyArg_ParseTupleAndKeywords(args, kwargs, "|iiif", kwlist, &tempQuality, &width, &height, &rate, &raw);
    
    // set quality
    if (tempQuality < 10){
        quality = 10;
    }else if (tempQuality > 100){
        quality = 100;
    }else{
        quality = tempQuality;
    }
    
    
    // set lastStreamImage time
    gettimeofday(&lastStreamImage, NULL);
    
    // set dispmanx display
    display = vc_dispmanx_display_open(screen);
    ret = vc_dispmanx_display_get_info(display, &info);
    assert(ret == 0);
    
    // set output height and width
    if (width > 0){
        info.width = width;
    }
    if (height > 0){
        info.height = height;
    }
    
   
    // DispmanX expects buffer rows need to be aligned to a 32 bit boundary
    pitch = ALIGN_UP(2 * info.width, 32);
     // output type
    type = VC_IMAGE_RGB565;
    
    // DISPMANX resource handle
    resource = vc_dispmanx_resource_create(
        type, info.width, info.height, &vc_image_ptr
        );
    vc_dispmanx_rect_set(&rect, 0, 0, info.width, info.height);
    image = calloc(1, pitch * info.height);
    buffer = malloc(pitch * info.height);
    
    initialized = true;
    Py_INCREF(Py_None);
    return Py_None;
}

/*
STREAM
----------
Must call Init first!
Stream will return a byte array of the image
rate argument limits the speed to conserve CPU power
*/
static PyObject *
_stream(PyObject *self) 
{
    
    // check if user initialized stream
    if (initialized == false){
        printf("You need to initialize the stream first!\nscreencap.init(quality, width, height, rate, raw_format)");
        Py_INCREF(Py_None);
        return Py_None;
    }
    
    // set current time
    gettimeofday(&currentTime, NULL);
    float timer = (currentTime.tv_sec - lastStreamImage.tv_sec) + ((currentTime.tv_usec - lastStreamImage.tv_usec) / 1000000.0f);
    
    if (timer > rate){
        VC_IMAGE_TRANSFORM_T transform = 0;
        vc_dispmanx_snapshot(display, resource, transform);
        vc_dispmanx_resource_read_data(resource, &rect, image, info.width * 2);
        
        // return RGB565 if user initialized raw_format
        if (raw != 0){
            gettimeofday(&lastStreamImage, NULL);
            return Py_BuildValue("s#", image, pitch * info.height);
        }
        
        // Begin initializing JPEG Compressor
        unsigned long buffer_size = 0;
        struct jpeg_compress_struct cinfo;
        struct jpeg_error_mgr jerr;
        cinfo.err = jpeg_std_error(&jerr);
        jpeg_create_compress(&cinfo);
        jpeg_mem_dest(&cinfo, &buffer, &buffer_size);
        

        JSAMPROW row_pointer[1];
        
        // JPEG Info
        cinfo.image_width = info.width;
        cinfo.image_height = info.height;
        cinfo.input_components = 3;
        cinfo.in_color_space = JCS_RGB;

        jpeg_set_defaults(&cinfo);
        jpeg_set_quality(&cinfo, quality, TRUE);
        jpeg_start_compress(&cinfo, TRUE);

        int row_stride = cinfo.image_width * 3;
        
        // Read each scanline into JPEG Compressor
        while (cinfo.next_scanline < cinfo.image_height) {
            unsigned char row[row_stride];
            unsigned char *dst = &row[0];
            uint16_t *src = (uint16_t*)(image + pitch * cinfo.next_scanline);
            
            for (int x = 0; x < cinfo.image_width; x++, src++) {
                *dst++ = C565_red(*src);
                *dst++ = C565_green(*src);
                *dst++ = C565_blue(*src);
            }
            row_pointer[0] = row;
            jpeg_write_scanlines(&cinfo, row_pointer, 1);
        }
        
        // finish and cleanup compression
        jpeg_finish_compress(&cinfo);
        jpeg_destroy_compress(&cinfo);
        
        // set lastStreamImage time and return byte Array
        gettimeofday(&lastStreamImage, NULL);
        return Py_BuildValue("s#", buffer, buffer_size);
    }
    
    // sleep 10 milliseconds to conserve cpu
    usleep(10 * 1000);
 
    // return nothing if it's not time to get another frame
    Py_INCREF(Py_None);
    return Py_None;
}

/*
END
-----
Cleanup various aspects of Stream method
*/
static PyObject *
_streamEnd(PyObject *self) 
{
    display = 0;
    ret = vc_dispmanx_resource_delete(resource);
    assert(ret == 0);

    ret = vc_dispmanx_display_close(display);
    assert(ret == 0);
    
    free(image);
    free(buffer);
    
    return Py_BuildValue("");
}

/*
GRAB
-------
Arguments:
quality - 10 to 100 jpeg quality control
file - Save to file instead of returning image byte array

if file argument is omitted, then a byte array of the image is returned
which in turn can be written to a file via usual python methods
*/
static PyObject *
_grab(PyObject *self, PyObject *args, PyObject *kwargs) 
{
    
    int quality = 75;
    uint32_t screen = 0;
    char* filename = NULL;
    FILE * outfile = NULL;
    
    int width = -1;
    int height = -1;
    
    static char *kwlist[] = {
        "quality",
        "width",
        "height",
        "screen", // screen # to capture
        "file",
        NULL
    };
    
    // parse arguments
    PyArg_ParseTupleAndKeywords(args, kwargs, "|iiiis", kwlist, &quality, &width, &height, &screen, &filename);
    
    // set quality
    if (quality < 10){
        quality = 10;
    }else if (quality > 100){
        quality = 100;
    }

    // set display
    DISPMANX_DISPLAY_HANDLE_T display = vc_dispmanx_display_open(screen);
    DISPMANX_MODEINFO_T info;

    int ret = vc_dispmanx_display_get_info(display, &info);
    assert(ret == 0);
    
    // set output height and width
    if (width > 0){
        info.width = width;
    }
    if (height > 0){
        info.height = height;
    }

    // DispmanX expects buffer rows need to be aligned to a 32 bit boundary
    int pitch = ALIGN_UP(2 * info.width, 32);

    // set image type 
    VC_IMAGE_TYPE_T type = VC_IMAGE_RGB565;
    uint32_t vc_image_ptr;
    
    // Create DISPMANX resource
    DISPMANX_RESOURCE_HANDLE_T resource = vc_dispmanx_resource_create(
        type, info.width, info.height, &vc_image_ptr
    );
    
    // Get the snapshot
    VC_IMAGE_TRANSFORM_T transform = 0;
    vc_dispmanx_snapshot(display, resource, transform);

    VC_RECT_T rect;
    vc_dispmanx_rect_set(&rect, 0, 0, info.width, info.height);
    
    // create image byte array
    unsigned char *image = malloc(pitch * info.height);
    assert(image);
    vc_dispmanx_resource_read_data(resource, &rect, image, info.width * 2);

    // cleanup DISPMANX resources
    ret = vc_dispmanx_resource_delete(resource);
    assert(ret == 0);

    ret = vc_dispmanx_display_close(display);
    assert(ret == 0);

     // Begin initializing JPEG Compressor
    unsigned char *buffer = malloc(pitch * info.height);
    unsigned long buffer_size = 0;
    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr jerr;
    cinfo.err = jpeg_std_error(&jerr);
    jpeg_create_compress(&cinfo);
    jpeg_mem_dest(&cinfo, &buffer, &buffer_size);
    
    // open output file if specified by user
    if (filename != NULL){
        if ((outfile = fopen(filename, "wb")) == NULL) {
            fprintf(stderr, "can't open %s\n", filename);
        }
        jpeg_stdio_dest(&cinfo, outfile);
    }
    
    JSAMPROW row_pointer[1];

    // JPEG Info
    cinfo.image_width = info.width;
    cinfo.image_height = info.height;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;

    // start JPEG compression
    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, quality, TRUE);
    jpeg_start_compress(&cinfo, TRUE);

    int row_stride = cinfo.image_width * 3;
    
    // read each scanline into compressor
    while (cinfo.next_scanline < cinfo.image_height) {
        unsigned char row[row_stride];
        unsigned char *dst = &row[0];
        uint16_t *src = (uint16_t*)(image + pitch * cinfo.next_scanline);
        
        for (int x = 0; x < cinfo.image_width; x++, src++) {
            *dst++ = (unsigned char) C565_red(*src);
            *dst++ = (unsigned char) C565_green(*src);
            *dst++ = (unsigned char) C565_blue(*src);
        }
        row_pointer[0] = row;
        jpeg_write_scanlines(&cinfo, row_pointer, 1);
    }
    
    // cleanup JPEG compressor objects
    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);
    
    
    PyObject* pythonReturnValue;
    
    if (outfile != NULL){
        fclose(outfile);
        Py_INCREF(Py_None);
        pythonReturnValue = Py_None;
    }else{
        pythonReturnValue = Py_BuildValue("s#", buffer, buffer_size);
    }
    
    /*free initial memory block*/
    free(image);
    free(buffer);
    
    return pythonReturnValue;

}

// python module methods
static PyMethodDef module_methods[] = {
   { "grab", (PyCFunction)_grab, METH_VARARGS | METH_KEYWORDS, NULL },
   { "init", (PyCFunction)_streamInit, METH_VARARGS | METH_KEYWORDS, NULL },
   { "end", (PyCFunction)_streamEnd,  METH_NOARGS, NULL },
   { "stream", (PyCFunction)_stream, METH_NOARGS, NULL },
   { NULL, NULL, 0, NULL }
};

void initscreencap(void) {
   bcm_host_init();
   Py_InitModule3("screencap", module_methods, "docstring...");
}
