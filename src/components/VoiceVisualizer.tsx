import React, { useEffect, useRef } from 'react';

interface VoiceVisualizerProps {
  isListening: boolean;
  analyser: AnalyserNode | null;
}

const VoiceVisualizer: React.FC<VoiceVisualizerProps> = ({ isListening, analyser }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    if (!analyser || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d')!;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      const { offsetWidth, offsetHeight } = canvas;
      canvas.width = offsetWidth * dpr;
      canvas.height = offsetHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    const draw = () => {
      animationRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const width = canvas.width / dpr;
      const height = canvas.height / dpr;
      const centerX = width / 2;
      const centerY = height / 2;

      // Energy level from frequencies
      let energy = 0;
      for (let i = 0; i < bufferLength; i++) energy += dataArray[i];
      energy = energy / (bufferLength * 255);

      const baseRadius = Math.min(width, height) * 0.22;
      const radius = baseRadius * (0.9 + energy * 0.6);

      // Create soft blob with Bezier curves
      const points = 16;
      const step = (Math.PI * 2) / points;

      ctx.save();
      const grad = ctx.createRadialGradient(centerX, centerY, radius * 0.2, centerX, centerY, radius);
      grad.addColorStop(0, isListening ? 'rgba(251, 146, 60, 0.9)' : 'rgba(251, 146, 60, 0.5)');
      grad.addColorStop(1, isListening ? 'rgba(249, 115, 22, 0.7)' : 'rgba(249, 115, 22, 0.35)');
      ctx.fillStyle = grad;

      ctx.beginPath();
      for (let i = 0; i <= points; i++) {
        const angle = i * step;
        const noise = Math.sin((Date.now() / 700) + i) * 10 + energy * 22;
        const r = radius + noise;
        const x = centerX + Math.cos(angle) * r;
        const y = centerY + Math.sin(angle) * r;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.quadraticCurveTo(centerX, centerY, x, y);
      }
      ctx.closePath();
      ctx.fill();

      // Concentric ripples
      const rings = 3;
      for (let r = 1; r <= rings; r++) {
        const alpha = isListening ? 0.15 : 0.08;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius + (r * 20), 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(251, 146, 60, ${alpha / r})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      ctx.restore();
    };

    draw();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [analyser, isListening]);

  return (
    <div className="relative h-40 bg-gradient-to-r from-orange-50 to-orange-100 border-t flex items-center justify-center overflow-hidden">
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
      />
      <div className="relative z-10 text-center">
        <div className="text-sm font-medium text-orange-600">
          {isListening ? 'Listening...' : 'Voice Mode Active'}
        </div>
        <div className="text-xs text-orange-500 mt-1">
          {isListening ? 'Speak now' : 'Click microphone to start'}
        </div>
      </div>
    </div>
  );
};

export default VoiceVisualizer;