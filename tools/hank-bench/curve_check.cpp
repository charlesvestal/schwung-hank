/* Measures OUR engine's decay time constant by fitting the slope of ln(envelope)
 * over -6..-40 dB. Slope-fitting, not threshold-crossing: a threshold needs a
 * reference peak, and a block-RMS peak is inflated ~10% by the partial cycle in
 * the first block, which biased an earlier version of this check by -8%. */
#include "../../src/dsp/hank_engine.h"
#include <stdio.h>
#include <math.h>
#include <vector>
int main(){
    const double SR=44100; const int N=128;
    printf("x tau_ours\n");
    for (int i=1;i<=40;i++){
        double x=i/40.0;
        hank::Engine e; hank::Params &p=e.params();
        p.op2_level=0; p.filter_on=0; p.voice_count=1;
        p.op1_a=0; p.op1_d=(float)x; p.op1_s=0; p.op1_r=0.5f; p.volume=0.5f;
        e.noteOn(60,127);
        std::vector<float> buf(N*2);
        std::vector<double> env; double mx=0;
        int blocks=(int)(60*SR/N);
        for(int b=0;b<blocks;b++){
            e.render(buf.data(),N);
            double s=0; for(int j=0;j<N*2;j+=2) s+=buf[j]*buf[j];
            double r=sqrt(s/N); env.push_back(r); if(r>mx) mx=r;
        }
        double hi=mx*0.5011872, lo=mx*0.01;      /* -6 dB, -40 dB */
        double sx=0,sy=0,sxy=0,sxx=0; int n=0;
        for(size_t k=0;k<env.size();k++){
            if(env[k]<=lo) break;
            if(env[k]>hi) continue;
            double t=(double)k*N/SR, y=log(env[k]);
            sx+=t; sy+=y; sxy+=t*y; sxx+=t*t; n++;
        }
        if(n<8){ printf("%.3f nan\n",x); continue; }
        double slope=(n*sxy-sx*sy)/(n*sxx-sx*sx);
        printf("%.3f %.6f\n", x, -1.0/slope);
    }
    return 0;
}
