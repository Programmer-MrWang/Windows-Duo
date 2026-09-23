"""离屏验证 Duo 折叠着色器: 合成测试纹理 → 渲染 → 输出 PNG (无需窗口)
用法: python offscreen_test.py [tilt_deg=60]
"""
import sys

import ctypes
from PIL import Image, ImageDraw
from PySide6.QtGui import QSurfaceFormat, QOffscreenSurface, QOpenGLContext
from PySide6.QtWidgets import QApplication
from OpenGL import GL

import glass_overlay as go
import gl_core

TILT_DEG = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
W, H = 960, 600


def make_test_texture():
    """合成测试图: 渐变底 + 网格 + 色块, 方便判断模糊/翻转/取样方向"""
    img = Image.new("RGB", (1920, 1200))
    dr = ImageDraw.Draw(img)
    for x in range(0, 1920, 4):
        c = (int(255 * x / 1920), 40, int(255 - 255 * x / 1920))
        dr.line([(x, 0), (x, 1200)], fill=c)
    for gx in range(0, 1920, 120):
        dr.line([(gx, 0), (gx, 1200)], fill=(255, 255, 255), width=3)
    for gy in range(0, 1200, 120):
        dr.line([(0, gy), (1920, gy)], fill=(255, 255, 255), width=3)
    dr.rectangle([100, 100, 300, 250], fill=(0, 200, 0))
    dr.rectangle([1600, 900, 1850, 1100], fill=(255, 255, 0))
    return img


def main():
    fmt = go._make_format()
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication(sys.argv)

    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    ctx = QOpenGLContext()
    ctx.setFormat(fmt)
    assert ctx.create(), "context create failed"
    assert ctx.makeCurrent(surface), "makeCurrent failed"

    prog = gl_core.compile_program()

    # 测试纹理 + mipmap
    img = make_test_texture()
    tex = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
    GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, img.width, img.height, 0,
                    GL.GL_RGB, GL.GL_UNSIGNED_BYTE, img.tobytes())
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
    GL.glGenerateMipmap(GL.GL_TEXTURE_2D)

    # FBO
    fbo = GL.glGenFramebuffers(1)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
    out_tex = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, out_tex)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, W, H, 0, GL.GL_RGBA,
                    GL.GL_UNSIGNED_BYTE, None)
    GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0,
                              GL.GL_TEXTURE_2D, out_tex, 0)
    assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) == GL.GL_FRAMEBUFFER_COMPLETE

    vao, _ = gl_core.make_quad()
    GL.glViewport(0, 0, W, H)
    GL.glUseProgram(prog)
    GL.glActiveTexture(GL.GL_TEXTURE0)
    GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
    # 参数一律从 config.json 读 (唯一参数入口), 不要在测试里硬编码
    tex_w, tex_h = img.width, img.height
    gl_core.set_uniforms(
        prog, tex_w, tex_h,
        tilt=TILT_DEG * 3.14159265 / 180.0,
        eye_z=float(go.CFG.get("eye_dist_h", 2.0)) * tex_h,
        spread=go.CFG.get("blur_spread", 0.42),
        dark=go.CFG.get("darkening", 0.001),
        max_taps=int(go.CFG.get("max_taps", 32)),
    )
    gl_core.draw_quad(vao)
    GL.glFlush()

    data = GL.glReadPixels(0, 0, W, H, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    out = Image.frombytes("RGB", (W, H), data).transpose(Image.FLIP_TOP_BOTTOM)
    out_path = "offscreen_result.png"
    out.save(out_path)
    print(f"[offscreen] tilt={TILT_DEG}° -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())