"use client";

import { useEffect } from "react";

const base_api =
  //process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  "https://outspoken-pandemic-surfer.ngrok-free.dev"

export default function BackgroundUpdater() {
  useEffect(() => {
    const update = async () => {
      try {
        const response = await fetch(`${base_api}/api/predictor/update`, {
          headers: {
            "ngrok-skip-browser-warning": "true",
          },
        });

        if (!response.ok) {
          console.warn("Background update failed:", response.status);
        }
      } catch (err) {
        console.warn("Background update error:", err);
      }
    };

    // Run once immediately
    update();

    // Then every minute
    const interval = setInterval(update, 60000);

    return () => clearInterval(interval);
  }, []);

  return null;
}
