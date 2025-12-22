import Link from "next/link";
import { Play, PenLine, Video, Film } from 'lucide-react';

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 text-center bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-purple-400 to-pink-400 text-transparent bg-clip-text">
        AI Video Factory
      </h1>
      <p className="text-xl mb-8 max-w-2xl text-gray-400">
        Generate viral vertical micro-dramas with AI. Create single episodes or entire series in minutes.
      </p>

      <Link
        href="/generate"
        className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white px-8 py-4 rounded-xl font-medium text-lg hover:opacity-90 transition-all hover:scale-105 shadow-lg shadow-purple-500/25"
      >
        <Play className="w-5 h-5" /> Start Creating
      </Link>

      <div className="mt-12 grid grid-cols-3 gap-8 text-center max-w-2xl">
        <div className="p-4">
          <PenLine className="w-8 h-8 mx-auto mb-2 text-purple-400" />
          <div className="text-white font-medium">Write Prompts</div>
          <div className="text-gray-500 text-sm">Describe your scenes</div>
        </div>
        <div className="p-4">
          <Video className="w-8 h-8 mx-auto mb-2 text-purple-400" />
          <div className="text-white font-medium">Generate Videos</div>
          <div className="text-gray-500 text-sm">AI creates clips</div>
        </div>
        <div className="p-4">
          <Film className="w-8 h-8 mx-auto mb-2 text-purple-400" />
          <div className="text-white font-medium">Build Series</div>
          <div className="text-gray-500 text-sm">Merge into series</div>
        </div>
      </div>
    </div>
  );
}
