#include <vintf/HalManifest.h>
#include <vintf/CompatibilityMatrix.h>
#include <vintf/parse_xml.h>
#include <vintf/parse_string.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
using namespace android::vintf;

// Use AOSP's existing test friend to invoke the real merge implementation.
// No compatibility logic, metadata provider or result is replaced.
namespace android::vintf {
struct LibVintfTest {
    static auto combine(HalManifest& d, std::vector<CompatibilityMatrix>& m, std::string& e) {
        auto level=d.kernel().has_value() ? d.kernel()->level() : Level::UNSPECIFIED;
        return CompatibilityMatrix::combine(d.level(),level,&m,&e);
    }
    static auto combineDevice(std::vector<CompatibilityMatrix>& m, std::string& e) {
        return CompatibilityMatrix::combineDeviceMatrices(&m,&e);
    }
};
}

template<class T> T read(const char* path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error(std::string("Cannot open ")+path);
    std::stringstream s; s << f.rdbuf();
    T value; std::string err;
    if (!fromXml(&value, s.str(), &err)) throw std::runtime_error(std::string(path)+": "+err);
    return value;
}

int main(int argc, char** argv) {
    try {
        if (argc==4 && std::string(argv[1])=="--roundtrip-manifest") {
            auto m=read<HalManifest>(argv[2]);
            std::ofstream f(argv[3]); f << toXml(m); return f ? 0 : 2;
        }
        if (argc==4 && std::string(argv[1])=="--roundtrip-matrix") {
            auto m=read<CompatibilityMatrix>(argv[2]);
            std::ofstream f(argv[3]); f << toXml(m); return f ? 0 : 2;
        }
        HalManifest device, framework;
        bool haveDevice=false, haveFramework=false;
        std::vector<CompatibilityMatrix> fm, dm;
        for (int i=1; i<argc; i+=2) {
            if (i+1>=argc) throw std::runtime_error("Expected option/path pairs");
            std::string opt=argv[i], err;
            if (opt=="--device" || opt=="--framework") {
                auto m=read<HalManifest>(argv[i+1]);
                auto &dest = opt=="--device" ? device : framework;
                auto &have = opt=="--device" ? haveDevice : haveFramework;
                if (!have) {dest=std::move(m); have=true;}
                else if (!dest.addAll(&m, &err)) throw std::runtime_error(std::string(argv[i+1])+": "+err);
            } else if (opt=="--framework-matrix") fm.push_back(read<CompatibilityMatrix>(argv[i+1]));
            else if (opt=="--device-matrix") dm.push_back(read<CompatibilityMatrix>(argv[i+1]));
            else throw std::runtime_error("Unknown option "+opt);
        }
        if (!haveDevice || !haveFramework || fm.empty() || dm.empty()) throw std::runtime_error("Missing manifest/matrix");
        std::string err;
        auto combined=LibVintfTest::combine(device,fm,err);
        if (!combined) throw std::runtime_error("Framework matrix merge: "+err);
        auto deviceMatrix=LibVintfTest::combineDevice(dm,err);
        if (!deviceMatrix) throw std::runtime_error("Device matrix merge: "+err);
        bool a=device.checkCompatibility(*combined,&err);
        std::cout << "device_to_framework=" << a << "\n" << err << "\n";
        err.clear();
        bool b=framework.checkCompatibility(*deviceMatrix,&err);
        std::cout << "framework_to_device=" << b << "\n" << err << "\n";
        std::cout << "scope=libvintf core manifest/matrix checks; not full checkvintf, runtime or registration\n";
        return a && b ? 0 : 1;
    } catch(const std::exception& e) {std::cerr << e.what() << "\n"; return 2;}
}
