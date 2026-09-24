// SPDX-License-Identifier: Apache-2.0
// Run against the locked upstream Utils.cpp, independent of Android hardware.
#include "Utils.h"
#include <cassert>
#include <cstdint>
#include <iostream>

using namespace aidl::android::hardware::light;

int main() {
    for (uint32_t maximum : {255u, 4095u}) {
        assert(scaleBrightness(0, maximum) == 0);
        assert(scaleBrightness(255, maximum) == maximum);
        uint32_t previous = 0;
        for (unsigned value = 0; value < 256; ++value) {
            const auto scaled = scaleBrightness(value, maximum);
            assert(scaled >= previous && scaled <= maximum);
            if (value != 0) assert(scaled > 0);
            previous = scaled;
            const uint32_t argb = 0xff000000u | (value << 16) | (value << 8) | value;
            assert(rgb(argb).toBrightness() == value);
        }
    }
    assert(rgb(0xff000000u).toBrightness() == 0);
    assert(rgb(0xffffffffu).toBrightness() == 255);
    std::cout << "PASS: 512 brightness mappings, range, monotonicity, endpoints and grayscale\n";
}
