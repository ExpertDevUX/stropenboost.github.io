# StrophenBoost Streaming Setup Guide

## OBS Studio Configuration

### Step 1: Get Your Stream Key
1. Log in to your StrophenBoost account
2. Go to Dashboard → Stream Settings
3. Copy your unique RTMP Stream Key

### Step 2: Configure OBS Studio
1. Open OBS Studio
2. Go to **Settings** → **Stream**
3. Set the following configuration:

```
Service: Custom...
Server: rtmp://your-domain.com:1935/live
Stream Key: [Your StrophenBoost Stream Key]
```

### Recommended OBS Settings for Best Quality

#### Video Settings
```
Base (Canvas) Resolution: 1920x1080
Output (Scaled) Resolution: 1920x1080 (or 1280x720 for lower bandwidth)
Common FPS Values: 30 or 60
```

#### Output Settings (Advanced Mode)
```
Output Mode: Advanced
Encoder: x264 (CPU) or NVENC H.264 (GPU)
Rate Control: CBR
Bitrate: 2500 Kbps (for 1080p30) or 1500 Kbps (for 720p30)
Keyframe Interval: 2 seconds
Preset: veryfast (for x264)
Profile: high
Tune: (none)
```

#### Audio Settings
```
Sample Rate: 44.1 kHz
Channels: Stereo
Bitrate: 128 kbps
```

## vMix Configuration

### Step 1: Stream Output Setup
1. Open vMix
2. Go to **Settings** → **Outputs** → **Stream**
3. Configure the following:

```
Destination: Custom RTMP Server
URL: rtmp://your-domain.com:1935/live/[Your Stream Key]
Quality: High (or customize based on bandwidth)
```

### Step 2: Recommended vMix Settings
```
Format: MP4
Video Codec: H.264
Audio Codec: AAC
Frame Rate: 30fps
Video Bitrate: 2500 kbps
Audio Bitrate: 128 kbps
Resolution: 1920x1080 or 1280x720
```

## Wirecast Configuration

### Setup Instructions
1. Open Wirecast
2. Go to **Output** → **Output Settings**
3. Select **RTMP Server** and configure:

```
Address: rtmp://your-domain.com:1935/live
Stream: [Your StrophenBoost Stream Key]
Username: (leave blank)
Password: (leave blank)
```

## XSplit Configuration

### Streaming Setup
1. Open XSplit Broadcaster
2. Go to **Outputs** → **Set up a new output**
3. Choose **Custom RTMP**:

```
Name: StrophenBoost
RTMP URL: rtmp://your-domain.com:1935/live
Stream Name/Key: [Your Stream Key]
```

## FFmpeg Command Line

For advanced users or automated streaming:

```bash
ffmpeg -re -i input.mp4 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -b:v 2500k -maxrate 2500k -bufsize 5000k \
  -pix_fmt yuv420p -g 60 -c:a aac -b:a 128k \
  -ar 44100 -f flv \
  rtmp://your-domain.com:1935/live/YOUR_STREAM_KEY
```

## Mobile Streaming Apps

### iOS Apps
- **Larix Broadcaster**: Professional RTMP streaming
- **Live:Air Solo**: Simple live streaming
- **Streamlabs Mobile**: User-friendly interface

### Android Apps
- **Larix Broadcaster**: Cross-platform professional app
- **CameraFi Live**: Easy mobile streaming
- **Streamlabs Mobile**: Complete streaming solution

### Mobile App Configuration
```
RTMP URL: rtmp://your-domain.com:1935/live
Stream Key: [Your StrophenBoost Stream Key]
Video Quality: 720p30 (recommended for mobile)
Bitrate: 1500-2000 kbps
```

## Network Requirements

### Minimum Requirements
- **Upload Speed**: 3 Mbps for 720p, 5 Mbps for 1080p
- **Latency**: < 50ms to streaming server
- **Connection**: Stable wired connection preferred

### Recommended Settings by Resolution

| Resolution | Frame Rate | Video Bitrate | Audio Bitrate | Total Bandwidth |
|------------|------------|---------------|---------------|-----------------|
| 720p       | 30fps      | 1500-2000k    | 128k          | 2-3 Mbps        |
| 720p       | 60fps      | 2000-2500k    | 128k          | 3-4 Mbps        |
| 1080p      | 30fps      | 2500-3000k    | 128k          | 4-5 Mbps        |
| 1080p      | 60fps      | 4000-5000k    | 128k          | 6-7 Mbps        |

## Troubleshooting

### Common Issues

#### Connection Failed
1. Check your internet connection
2. Verify the RTMP URL is correct
3. Ensure port 1935 is not blocked by firewall
4. Try a different streaming server if available

#### Poor Stream Quality
1. Reduce bitrate settings
2. Lower resolution (1080p → 720p)
3. Decrease frame rate (60fps → 30fps)
4. Check CPU/GPU usage in streaming software

#### Audio Issues
1. Set audio sample rate to 44.1 kHz
2. Use stereo channels
3. Set audio bitrate to 128 kbps
4. Check audio device settings

#### Dropped Frames
1. Lower video bitrate
2. Change encoder preset to "veryfast"
3. Close unnecessary applications
4. Use hardware encoding if available

### Stream Key Management
- Keep your stream key private
- Regenerate key if compromised
- Use different keys for different streams
- Monitor unauthorized usage

### Testing Your Stream
1. Start streaming with test content
2. Check stream status in dashboard
3. Verify video/audio quality
4. Test different resolutions and bitrates
5. Monitor viewer experience

## Advanced Features

### Multi-bitrate Streaming
StrophenBoost automatically generates multiple quality levels:
- Source quality (your original stream)
- 720p version for standard viewers
- 480p version for mobile/low bandwidth
- Audio-only version

### Low Latency Mode
Enable low latency in your streaming software:
- Use "zerolatency" tune in x264
- Reduce keyframe interval to 1-2 seconds
- Use CBR rate control
- Minimize buffering settings

### Stream Analytics
Monitor your stream performance:
- Real-time viewer count
- Bandwidth usage
- Stream health metrics
- Quality indicators
- Geographic viewer distribution

## Professional Tips

### Content Creation
1. **Plan Your Content**: Prepare talking points and activities
2. **Audio Quality**: Invest in a good microphone
3. **Lighting**: Ensure proper lighting for video quality
4. **Background**: Use a clean, professional background
5. **Interaction**: Engage with your audience through chat

### Technical Best Practices
1. **Test Before Going Live**: Always test your setup
2. **Backup Internet**: Have a secondary connection ready
3. **Monitor Resources**: Watch CPU/GPU usage during streaming
4. **Stream Consistency**: Maintain regular streaming schedule
5. **Quality over Quantity**: Better to stream less frequently with high quality

### Growing Your Audience
1. **Consistent Schedule**: Stream at regular times
2. **Social Media**: Promote streams on other platforms
3. **Community Building**: Engage with viewers and build relationships
4. **Collaborations**: Work with other streamers
5. **Content Variety**: Mix different types of content

## Support

If you encounter issues:
1. Check this guide first
2. Visit our troubleshooting section
3. Contact StrophenBoost support
4. Join our community Discord
5. Check streaming software documentation

Remember: Streaming quality depends on your internet connection, hardware capabilities, and software configuration. Start with recommended settings and adjust based on your specific setup and audience feedback.