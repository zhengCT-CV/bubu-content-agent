import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17211d",
        paper: "#f6f3eb",
        sage: {
          50: "#f2f7f3",
          100: "#e0ece2",
          300: "#9fc2a7",
          500: "#4f8260",
          700: "#31553e",
          900: "#1b3124"
        },
        coral: "#e87558",
      },
      boxShadow: {
        soft: "0 20px 50px rgba(33, 49, 40, 0.08)",
      },
      fontFamily: {
        sans: ["Inter", "Microsoft YaHei", "PingFang SC", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;

