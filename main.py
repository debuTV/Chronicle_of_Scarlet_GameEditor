"""Chronicle of Scarlet 存档解密/回写工具。

文件格式分两层：
1. 外层是 Godot 的 FileAccessEncrypted 容器，文件头为 GDEC。
2. 内层是 Godot store_var(String) 写出的 Variant String，内容是 JSON 字符串。

这个脚本的职责很单一：
- .save -> .json：解密外层，再拆出内层 JSON。
- .json -> .save：把 JSON 按原格式重新打包，再加密回 .save。
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from Crypto.Cipher import AES


# AES CFB 的块大小固定为 16 字节。Godot 的 FileAccessEncrypted
# 在写入时会把明文补齐到 16 的倍数，但真正的原始长度仍然单独记录。
AES_BLOCK_SIZE = 16

# Godot FileAccessEncrypted 在无魔数模式下会写入 MD5/长度/IV/密文；
# 游戏实际保存时启用了魔数，因此文件前 4 字节固定是 GDEC。
ENCRYPTED_MAGIC = b"GDEC"

# 外层加密存档头的总长度：
# 4 字节魔数 + 16 字节明文 MD5 + 8 字节明文长度 + 16 字节 IV = 44。
SAVE_HEADER_SIZE = 44

# Godot Variant String 的最小头：
# 4 字节 variant_size + 4 字节 variant_type + 4 字节字符串长度。
VARIANT_HEADER_SIZE = 12

# Godot 的 Variant 数据以 4 字节对齐，字符串尾部会补 0 到 4 的倍数。
VARIANT_PADDING = 4

# Variant type 4 对应 String。这里的存档正文就是一个被 store_var 写出的字符串。
VARIANT_STRING_TYPE = 4

# 这是从游戏内 SaveManager.gd 里还原出的真实存档口令。
SAVE_PASSWORD = "NV91UE09G8G7DUJ37ZPCKBNRA0MQ8V8X"

# 游戏读取存档时还会校验 saveCode；不匹配的话，即使解密成功也不会让你载入。
SAVE_CODE = "wdmotaCollection96513"


def align_size(size: int, block_size: int) -> int:
    """把长度向上补齐到 block_size 的整数倍。"""

    return size + (-size % block_size)


def password_to_key(password: str) -> bytes:
    """把游戏里的口令转换成 Godot 实际使用的 32 字节 AES key。

    FileAccess.open_encrypted_with_pass() 并不是直接拿原始密码做 AES key，
    而是先对密码做 MD5，拿到 32 个 ASCII 十六进制字符，再作为 32 字节 key 使用。
    """

    return hashlib.md5(password.encode("utf-8")).hexdigest().encode("ascii")


def decrypt_save_blob(blob: bytes, password: str) -> bytes:
    """解密整个 .save 文件，返回内层明文字节串。

    外层格式固定为：
    - 4 字节 GDEC
    - 16 字节明文 MD5
    - 8 字节明文长度（小端）
    - 16 字节 IV
    - N 字节 AES-CFB 密文，长度按 16 字节补齐
    """

    if not blob.startswith(ENCRYPTED_MAGIC):
        raise ValueError("unexpected save header, expected GDEC")

    expected_md5 = blob[4:20]
    plain_length = int.from_bytes(blob[20:28], "little")
    iv = blob[28:44]

    # Godot 写入时会把密文长度补到 AES block 的整数倍，所以这里要先按补齐长度截取密文，
    # 再在解密后按 plain_length 截断回真实明文。
    cipher_end = SAVE_HEADER_SIZE + align_size(plain_length, AES_BLOCK_SIZE)
    cipher_text = blob[SAVE_HEADER_SIZE:cipher_end]
    if len(cipher_text) != cipher_end - SAVE_HEADER_SIZE:
        raise ValueError("save file is truncated")

    plain = AES.new(password_to_key(password), AES.MODE_CFB, iv=iv, segment_size=128).decrypt(cipher_text)[:plain_length]

    # 游戏保存时会把明文 MD5 一起写进文件头，先校验一遍能更早发现密码不对或文件损坏。
    if hashlib.md5(plain).digest() != expected_md5:
        raise ValueError("save password is wrong or the file is corrupted")
    return plain


def encrypt_save_blob(plain: bytes, password: str, iv: bytes | None = None) -> bytes:
    """把明文字节串重新封装成 Godot 的 GDEC 存档格式。"""

    if iv is None:
        iv = os.urandom(16)
    if len(iv) != 16:
        raise ValueError("iv must be exactly 16 bytes")

    # 为了和 Godot 的 FileAccessEncrypted 行为一致，写出前把明文补齐到 16 的倍数；
    # 文件头里仍保留原始明文长度，读取时就能精确裁掉这些补位 0。
    padded_plain = plain.ljust(align_size(len(plain), AES_BLOCK_SIZE), b"\x00")
    cipher_text = AES.new(password_to_key(password), AES.MODE_CFB, iv=iv, segment_size=128).encrypt(padded_plain)
    return b"".join(
        [
            ENCRYPTED_MAGIC,
            hashlib.md5(plain).digest(),
            len(plain).to_bytes(8, "little"),
            iv,
            cipher_text,
        ]
    )


def unpack_variant_string(plain: bytes) -> str:
    """从 Godot Variant String 明文里拆出真正的 JSON 字符串。

    这里不是直接存的 UTF-8 JSON，而是 store_var(String) 产生的二进制结构：
    - variant_size: 当前 Variant 除自身这 4 字节外的总大小
    - variant_type: 应当是 4，表示 String
    - string_length: UTF-8 字节长度
    - string bytes
    - 0~3 字节对齐填充
    """

    if len(plain) < VARIANT_HEADER_SIZE:
        raise ValueError("decrypted payload is too short")

    variant_size = int.from_bytes(plain[:4], "little")
    variant_type = int.from_bytes(plain[4:8], "little")
    string_length = int.from_bytes(plain[8:12], "little")
    string_end = VARIANT_HEADER_SIZE + string_length
    if string_end > len(plain):
        raise ValueError("variant string payload is truncated")

    if variant_size != len(plain) - 4:
        raise ValueError("unexpected variant size header")
    if variant_type != VARIANT_STRING_TYPE:
        raise ValueError("unexpected variant type")

    # String 内容后面会补 0 到 4 字节对齐，所以不能写死成“必须只有一个 \x00”。
    padding = plain[string_end:]
    if padding != b"\x00" * (-string_length % VARIANT_PADDING):
        raise ValueError("unexpected variant string trailer")

    return plain[VARIANT_HEADER_SIZE:string_end].decode("utf-8")


def pack_variant_string(text: str) -> bytes:
    """把 JSON 文本重新封装成 Godot Variant String。"""

    raw = text.encode("utf-8")
    padding = b"\x00" * (-len(raw) % VARIANT_PADDING)
    variant_size = len(raw) + len(padding) + 8
    return b"".join(
        [
            variant_size.to_bytes(4, "little"),
            VARIANT_STRING_TYPE.to_bytes(4, "little"),
            len(raw).to_bytes(4, "little"),
            raw,
            padding,
        ]
    )


def load_save_json(path: Path) -> dict:
    """读取 .save 并返回解析后的 JSON 对象。"""

    plain = decrypt_save_blob(path.read_bytes(), SAVE_PASSWORD)
    data = json.loads(unpack_variant_string(plain))
    if not isinstance(data, dict):
        raise ValueError("save JSON root must be an object")
    return data


def decode_save_file(input_path: Path, output_path: Path) -> None:
    """把 .save 解码成格式化后的 .json 文件。"""

    output_path.write_text(json.dumps(load_save_json(input_path), ensure_ascii=False, indent=2), encoding="utf-8")


def encode_save_file(input_path: Path, output_path: Path) -> None:
    """把 .json 回写成游戏可读取的 .save 文件。"""

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("save JSON root must be an object")

    # 游戏会校验 saveCode；无论用户 JSON 里怎么写，这里都强制修正成游戏期望的常量。
    data["saveCode"] = SAVE_CODE
    plain = pack_variant_string(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    output_path.write_bytes(encrypt_save_blob(plain, SAVE_PASSWORD))


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。

    当前按用户要求，只保留 -i 和 -o 两个参数；模式由扩展名自动推断。
    """

    parser = argparse.ArgumentParser(
        description="Decode or re-encode Chronicle of Scarlet save files.",
        add_help=False,
    )
    parser.add_argument("-i", dest="input", default="motaSave16.save", help="Input file path.")
    parser.add_argument("-o", dest="output", default="mota.json", help="Output file path.")
    return parser


def infer_mode(input_path: Path, output_path: Path) -> str:
    """根据输入输出扩展名自动判断当前是解密还是回写。"""

    mode_map = {
        (".save", ".json"): "decode",
        (".json", ".save"): "encode",
    }
    mode = mode_map.get((input_path.suffix.lower(), output_path.suffix.lower()))
    if mode is None:
        raise ValueError("cannot infer mode from file extensions; use .save -> .json or .json -> .save")
    return mode


def main() -> None:
    """脚本入口。"""

    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    mode = infer_mode(input_path, output_path)
    if mode == "decode":
        decode_save_file(input_path, output_path)
        print(f"decoded {input_path} -> {output_path}")
        return

    encode_save_file(input_path, output_path)
    print(f"encoded {input_path} -> {output_path}")


if __name__ == "__main__":
    main()