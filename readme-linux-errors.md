## FIX

Was able to fix the error following this stack overflow [answer][https://stackoverflow.com/questions/72110384/libgl-error-mesa-loader-failed-to-open-iris].

I did the following, my conda environment is named `ring-env2`.

```
cd ~/anaconda3/envs/ring-env2/lib
mkdir backup 
mv libstd* backup
cp /usr/lib/x86_64-linux-gnu/libstdc++.so.6  ./ 
ln -s libstdc++.so.6 libstdc++.so
ln -s libstdc++.so.6 libstdc++.so.6.0.19
```

Then in ipython

```
import napari
import numpy as np
arr = np.random.random((100,100,100))
viewer = napari.Viewer()
viewer.add_image(arr)  # SUCCESS
```

## Notes

was
napari==0.3.7

new
napari==0.4.17

WARNING: composeAndFlush: makeCurrent() failed


tried 0.4.16 still broken

glxgears
Running synchronized to the vertical refresh.  The framerate should be
approximately the same as the monitor refresh rate.
389 frames in 5.0 seconds = 77.641 FPS

pip uninstall vispy
pip install napari=0.3.7

uses vispy==0.10.0

uses vispy-0.12.1


##

libGL error: MESA-LOADER: failed to open iris: /usr/lib/dri/iris_dri.so: cannot open shared object file: No such file or directory (search paths /usr/lib/x86_64-linux-gnu/dri:\$${ORIGIN}/dri:/usr/lib/dri, suffix _dri)
libGL error: failed to load driver: iris
libGL error: MESA-LOADER: failed to open iris: /usr/lib/dri/iris_dri.so: cannot open shared object file: No such file or directory (search paths /usr/lib/x86_64-linux-gnu/dri:\$${ORIGIN}/dri:/usr/lib/dri, suffix _dri)
libGL error: failed to load driver: iris
libGL error: MESA-LOADER: failed to open swrast: /usr/lib/dri/swrast_dri.so: cannot open shared object file: No such file or directory (search paths /usr/lib/x86_64-linux-gnu/dri:\$${ORIGIN}/dri:/usr/lib/dri, suffix _dri)
libGL error: failed to load driver: swrast


trying conda again after `conda install -c conda-forge napari`

## upgraded conda

conda update -n base -c defaults conda

## create new environment

conda create -y -n ring-env2 python=3.9


```
import napari
import numpy as np
arr = np.random.random((100,100,100))
viewer = napari.Viewer()
viewer.add_image(arr)  # fails
```

This is the error

```
libGL error: MESA-LOADER: failed to open iris: /usr/lib/dri/iris_dri.so: cannot open shared object file: No such file or directory (search paths /usr/lib/x86_64-linux-gnu/dri:\$${ORIGIN}/dri:/usr/lib/dri, suffix _dri)
libGL error: failed to load driver: iris
libGL error: MESA-LOADER: failed to open iris: /usr/lib/dri/iris_dri.so: cannot open shared object file: No such file or directory (search paths /usr/lib/x86_64-linux-gnu/dri:\$${ORIGIN}/dri:/usr/lib/dri, suffix _dri)
libGL error: failed to load driver: iris
libGL error: MESA-LOADER: failed to open swrast: /usr/lib/dri/swrast_dri.so: cannot open shared object file: No such file or directory (search paths /usr/lib/x86_64-linux-gnu/dri:\$${ORIGIN}/dri:/usr/lib/dri, suffix _dri)
libGL error: failed to load driver: swrast
WARNING: QOpenGLWidget: Failed to create context
WARNING: QOpenGLWidget: Failed to create context
WARNING: QOpenGLWidget: Failed to create context
Out[1]: <Image layer 'arr' at 0x7f388488da60>

In [2]: WARNING: QOpenGLWidget: Failed to create context
WARNING: composeAndFlush: QOpenGLContext creation failed
WARNING: composeAndFlush: makeCurrent() failed
WARNING: QOpenGLWidget: Failed to create context
WARNING: composeAndFlush: makeCurrent() failed
WARNING: composeAndFlush: makeCurrent() failed
WARNING: composeAndFlush: makeCurrent() failed
WARNING: composeAndFlush: makeCurrent() failed
```
