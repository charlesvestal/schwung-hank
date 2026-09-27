#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <time.h>
#include "plugin_api_v1.h"
static double now(){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1e3+t.tv_nsec/1e6;}
int main(int argc,char**argv){
    void*h=dlopen(argv[1],RTLD_NOW);
    typedef plugin_api_v2_t*(*Init)(const host_api_v1_t*);
    plugin_api_v2_t*api=((Init)dlsym(h,"move_plugin_init_v2"))(0);
    for(int a=2;a<argc;a++){
        double best=1e9; char buf[64]; int n=0;
        for(int i=0;i<5;i++){
            double t0=now();
            void*in=api->create_instance(argv[a],"{}");
            double dt=now()-t0;
            api->get_param(in,"preset_count",buf,sizeof buf); n=atoi(buf);
            api->destroy_instance(in);
            if(dt<best)best=dt;
        }
        printf("  %-28s preset_count=%-4d create_instance %6.2f ms\n",argv[a],n,best);
    }
    return 0;
}
