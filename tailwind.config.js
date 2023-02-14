/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/cryptoadvance/**/*.{html,js,jinja}"],
  theme: {
    fontFamily: {
      sans: ["Social", "sans-serif"],
    },
    extend: {
      colors: {
        dark: {
          50: "#E7E7E8",
          100: "#CFCFD0", // light text
          200: "#9F9FA1", // grey text
          300: "#6F7073",
          400: "#57585B", // grey text
          500: "#3F4044",
          600: "#2C2D31", // grey button
          700: "#1B1C21", // borders
          800: "#14151A", // card background
          900: "#0F1015", // background
        },
        // accent: "#0047FF",
        accent: "#2E5CFF",
        link: "#2997ff"
      },
    },
  },
  plugins: [],
};
