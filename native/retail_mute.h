#pragma once
#include <windows.h>
#include <mmdeviceapi.h>
#include <audiopolicy.h>
// Default audio session of this process only. No master-volume operation and
// no playback; called while still in POL, before FFXI startup audio can occur.
inline bool retailProcessAudio(bool applyMute) {
    HRESULT initialized=CoInitializeEx(nullptr,COINIT_MULTITHREADED);
    if(FAILED(initialized)&&initialized!=RPC_E_CHANGED_MODE)return false;
    IMMDeviceEnumerator* devices{};IMMDevice* device{};IAudioSessionManager2* sessions{};ISimpleAudioVolume* volume{};
    HRESULT hr=CoCreateInstance(__uuidof(MMDeviceEnumerator),nullptr,CLSCTX_INPROC_SERVER,__uuidof(IMMDeviceEnumerator),reinterpret_cast<void**>(&devices));
    bool noEndpoint=false;
    if(SUCCEEDED(hr)){hr=devices->GetDefaultAudioEndpoint(eRender,eConsole,&device);noEndpoint=hr==HRESULT_FROM_WIN32(ERROR_NOT_FOUND);}
    if(SUCCEEDED(hr))hr=device->Activate(__uuidof(IAudioSessionManager2),CLSCTX_INPROC_SERVER,nullptr,reinterpret_cast<void**>(&sessions));
    if(SUCCEEDED(hr))hr=sessions->GetSimpleAudioVolume(nullptr,0,&volume);
    if(SUCCEEDED(hr)&&applyMute)hr=volume->SetMute(TRUE,nullptr);
    BOOL muted=FALSE;if(SUCCEEDED(hr))hr=volume->GetMute(&muted);
    if(volume)volume->Release();if(sessions)sessions->Release();if(device)device->Release();if(devices)devices->Release();
    if(SUCCEEDED(initialized))CoUninitialize();
    return noEndpoint||(SUCCEEDED(hr)&&muted);
}
