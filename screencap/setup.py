from distutils.core import setup, Extension

module1 = Extension('screencap', 
                                sources = ['main.c'],
                                include_dirs = ['/opt/vc/include/', '/opt/vc/include/interface/vmcs_host/linux', '/opt/vc/include/interface/vcos/pthreads', '/opt/vc/include/interface/vmcs_host/linux '],
                                library_dirs = ['/opt/vc/lib/'],
                                libraries = ['GLESv2', 'EGL', 'openmaxil', 'bcm_host', 'vcos', 'vchiq_arm', 'pthread', 'rt', 'jpeg'],
                                define_macros = [('HAVE_LIBBCM_HOST',), ('USE_EXTERNAL_LIBBCM_HOST',), ('USE_VCHIQ_ARM',)],
                                extra_compile_args=['-std=gnu99', '-fgnu89-inline']
                                )


setup(name='screencap', 
            version='1.0',
            ext_modules=[module1]
      )