#pragma once
// Desktop adapter only. Firmware test_hooks.cpp is compiled unchanged.
#include <cstdint>
#include <cstdio>
#include <string>
#include <chrono>
#include <thread>
#include <cstdarg>
inline uint32_t millis() {
    static auto start = std::chrono::steady_clock::now();
    return (uint32_t)std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
}
inline void delay(uint32_t ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }
struct HostSerial {
    std::string input, output;
    size_t pos = 0;
    int available() { return (int)(input.size()-pos); }
    char read() { return input[pos++]; }
    void feed(const std::string &s) { input=s+"\n"; pos=0; }
    void print(char c) { output+=c; }
    void print(const char *s) { output+=s; }
    void print(int n) { output+=std::to_string(n); }
    void println(const char *s) { output+=s; output+='\n'; }
    void printf(const char *fmt, ...) {
        char buf[4096]; va_list args; va_start(args,fmt);
        vsnprintf(buf,sizeof(buf),fmt,args); va_end(args); output+=buf;
    }
    void flush() { std::fwrite(output.data(),1,output.size(),stdout); std::fflush(stdout); output.clear(); }
};
extern HostSerial Serial;
