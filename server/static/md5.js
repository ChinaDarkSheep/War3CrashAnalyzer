/* 轻量 MD5 实现：作者查询页在浏览器本地计算地图文件哈希，文件不会上传。 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.MD5 = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    var SHIFTS = [
        7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
        5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
        4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
        6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21
    ];

    var K = [
        0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee,
        0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
        0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be,
        0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
        0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa,
        0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
        0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed,
        0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
        0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c,
        0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
        0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05,
        0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
        0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039,
        0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
        0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1,
        0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391
    ];

    function rotateLeft(value, shift) {
        return ((value << shift) | (value >>> (32 - shift))) >>> 0;
    }

    function md5(input) {
        var bytes;
        if (input instanceof ArrayBuffer) {
            bytes = new Uint8Array(input);
        } else if (ArrayBuffer.isView(input)) {
            bytes = new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
        } else {
            throw new TypeError('MD5 expects an ArrayBuffer or typed array');
        }

        var length = bytes.length;
        var paddedLength = Math.ceil((length + 9) / 64) * 64;
        var padded = new Uint8Array(paddedLength);
        padded.set(bytes);
        padded[length] = 0x80;

        var view = new DataView(padded.buffer);
        view.setUint32(paddedLength - 8, (length * 8) >>> 0, true);
        view.setUint32(paddedLength - 4, Math.floor(length / 0x20000000) >>> 0, true);

        var a0 = 0x67452301;
        var b0 = 0xefcdab89;
        var c0 = 0x98badcfe;
        var d0 = 0x10325476;
        var words = new Uint32Array(16);

        for (var offset = 0; offset < paddedLength; offset += 64) {
            for (var i = 0; i < 16; i++) {
                words[i] = view.getUint32(offset + i * 4, true);
            }
            var a = a0;
            var b = b0;
            var c = c0;
            var d = d0;

            for (var step = 0; step < 64; step++) {
                var f;
                var g;
                if (step < 16) {
                    f = (b & c) | (~b & d);
                    g = step;
                } else if (step < 32) {
                    f = (d & b) | (~d & c);
                    g = (5 * step + 1) & 15;
                } else if (step < 48) {
                    f = b ^ c ^ d;
                    g = (3 * step + 5) & 15;
                } else {
                    f = c ^ (b | ~d);
                    g = (7 * step) & 15;
                }
                f = (f + a + K[step] + words[g]) >>> 0;
                a = d;
                d = c;
                c = b;
                b = (b + rotateLeft(f, SHIFTS[step])) >>> 0;
            }

            a0 = (a0 + a) >>> 0;
            b0 = (b0 + b) >>> 0;
            c0 = (c0 + c) >>> 0;
            d0 = (d0 + d) >>> 0;
        }

        var digest = new Uint8Array(16);
        var digestView = new DataView(digest.buffer);
        digestView.setUint32(0, a0, true);
        digestView.setUint32(4, b0, true);
        digestView.setUint32(8, c0, true);
        digestView.setUint32(12, d0, true);

        var hex = '';
        for (var j = 0; j < digest.length; j++) {
            hex += digest[j].toString(16).padStart(2, '0');
        }
        return hex;
    }

    return md5;
}));
