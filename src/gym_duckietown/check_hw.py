from ctypes import c_char_p, cast
from typing import Dict
import json
import pyglet

prev_headless = pyglet.options["headless"]
pyglet.options["headless"] = True
from pyglet import gl
pyglet.options["headless"] = prev_headless

__all__ = ["get_graphics_information"]


def get_graphics_information() -> Dict:
    prev_headless = pyglet.options["headless"]
    try:
        pyglet.options["headless"] = True
        options = {
            "vendor": gl.GL_VENDOR,
            "renderer": gl.GL_RENDERER,
            "version": gl.GL_VERSION,
            "shading-language-version": gl.GL_SHADING_LANGUAGE_VERSION,
            # 'extensions': gl.GL_EXTENSIONS
        }
    
        results = {}
        for o, code in options.items():
            a = gl.glGetString(code)
            
            b: bytes = cast(a, c_char_p).value
            res = b.decode()
            results[o] = res
        return results
    finally: 
        pyglet.options["headless"] = prev_headless


def main():
    print(json.dumps(get_graphics_information(), indent=2))


if __name__ == "__main__":
    main()
