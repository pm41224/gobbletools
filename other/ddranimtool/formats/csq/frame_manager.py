import logging
import os
import shutil
import tempfile

from PIL import Image

import numpy as np

logger = logging.getLogger("ddranimtool." + __name__)


class FrameManager:
    def __init__(self, cache_folder, raw_video_folder="", jpsxdec_jar_path=None):
        self.video_cache = {}
        self.frame_cache = {}
        self.cache_folder = os.path.abspath(cache_folder)
        self.raw_video_folder = os.path.abspath(raw_video_folder) if raw_video_folder else ""
        self.jpsxdec_jar_path = os.path.abspath(jpsxdec_jar_path) if jpsxdec_jar_path is not None else None

    def dump_raw_frame(self, chunk, output_filename):
        JPSXDEC_COMMAND = "java -jar \"%s\" -f \"{0}\" -static bs -dim {1}x{2} -fmt png -quality psx" % self.jpsxdec_jar_path

        # This is stupid but jPSXdec doesn't actually have a way to save to a specific directory from command line,
        # so change directories to the temporary folder until the end of the function and then restore the old directory
        cwd = os.getcwd()

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".bin") as raw_frame_file:
            os.chdir(os.path.dirname(raw_frame_file.name))

            raw_frame_file.write(chunk)
            converted_frame_path = os.path.splitext(raw_frame_file.name)[0] + ".png"

            cmd = JPSXDEC_COMMAND.format(raw_frame_file.name, 304, 176)
            os.system(cmd)

            shutil.move(converted_frame_path, output_filename)

        os.chdir(cwd)

    def get_cached_frames(self, filename):
        self.video_cache[filename] = []

        basename = os.path.basename(os.path.splitext(filename)[0])
        frame_idx = 0

        while True:
            output_filename = os.path.join(self.cache_folder, "%s_%04d.png" % (basename, frame_idx))

            if not os.path.exists(output_filename):
                break

            with Image.open(output_filename) as inframe:
                self.frame_cache[output_filename] = (inframe.tobytes(), inframe.size, inframe.mode)

                self.video_cache[filename].append(
                    np.asarray(Image.frombytes(
                        mode=self.frame_cache[output_filename][2],
                        size=self.frame_cache[output_filename][1],
                        data=self.frame_cache[output_filename][0]
                    ))
                )

            frame_idx += 1


    def get_raw_frames(self, filename):
        req_frames = []

        os.makedirs(self.cache_folder, exist_ok=True)

        if not filename in self.video_cache:
            self.get_cached_frames(filename)

        if not self.video_cache.get(filename, []):
            # Only deal with jPSXdec if we need to dump a video
            assert (self.jpsxdec_jar_path is not None)

            self.video_cache[filename] = []

            input_filename = os.path.join(self.raw_video_folder, filename)
            logger.debug("Loading frames for %s" % input_filename)

            if not os.path.exists(input_filename):
                logger.error("Could not find %s" % input_filename)
            assert (os.path.exists(input_filename) == True)

            with open(input_filename, "rb") as infile:
                data = bytearray(infile.read())
                chunks = [data[i:i+0x2000] for i in range(0, len(data), 0x2000)]

                for frame_idx in range(len(chunks)):
                    output_filename = os.path.join(self.cache_folder, "%s_%04d.png" % (
                        os.path.basename(os.path.splitext(filename)[0]), frame_idx))

                    if output_filename not in self.frame_cache:
                        if not os.path.exists(output_filename):
                            self.dump_raw_frame(chunks[frame_idx], output_filename)

                        with Image.open(output_filename) as inframe:
                            self.frame_cache[output_filename] = (inframe.tobytes(), inframe.size, inframe.mode)

                    self.video_cache[filename].append(
                        np.asarray(Image.frombytes(
                            mode=self.frame_cache[output_filename][2],
                            size=self.frame_cache[output_filename][1],
                            data=self.frame_cache[output_filename][0]
                        ))
                    )

        req_frames += self.video_cache[filename]

        return req_frames
