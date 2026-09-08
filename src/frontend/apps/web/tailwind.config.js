/** @type {import('tailwindcss').Config} */
module.exports = {
	darkMode: ["class"],
	content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
 
    // Or if using `src` directory:
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "./apps/web/src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
	theme: {
    	extend: {
    		borderRadius: {
    			lg: 'var(--radius)',
    			md: 'calc(var(--radius) - 2px)',
    			sm: 'calc(var(--radius) - 4px)'
    		},
    		colors: {
    			background: 'hsl(var(--background))',
    			foreground: 'hsl(var(--foreground))',
    			card: {
    				DEFAULT: 'hsl(var(--card))',
    				foreground: 'hsl(var(--card-foreground))'
    			},
    			popover: {
    				DEFAULT: 'hsl(var(--popover))',
    				foreground: 'hsl(var(--popover-foreground))'
    			},
    			primary: {
    				DEFAULT: 'hsl(var(--primary))',
    				foreground: 'hsl(var(--primary-foreground))'
    			},
    			secondary: {
    				DEFAULT: 'hsl(var(--secondary))',
    				foreground: 'hsl(var(--secondary-foreground))'
    			},
    			muted: {
    				DEFAULT: 'hsl(var(--muted))',
    				foreground: 'hsl(var(--muted-foreground))'
    			},
    			accent: {
    				DEFAULT: 'hsl(var(--accent))',
    				foreground: 'hsl(var(--accent-foreground))'
    			},
    			destructive: {
    				DEFAULT: 'hsl(var(--destructive))',
    				foreground: 'hsl(var(--destructive-foreground))'
    			},
    			border: 'hsl(var(--border))',
    			input: 'hsl(var(--input))',
    			ring: 'hsl(var(--ring))',
    			chart: {
    				'1': 'hsl(var(--chart-1))',
    				'2': 'hsl(var(--chart-2))',
    				'3': 'hsl(var(--chart-3))',
    				'4': 'hsl(var(--chart-4))',
    				'5': 'hsl(var(--chart-5))'
    			},
    			automl: {
    				canvas: 'hsl(var(--automl-canvas) / <alpha-value>)',
    				surface: 'hsl(var(--automl-surface) / <alpha-value>)',
    				'surface-muted': 'hsl(var(--automl-surface-muted) / <alpha-value>)',
    				line: 'hsl(var(--automl-line) / <alpha-value>)',
    				ink: 'hsl(var(--automl-ink) / <alpha-value>)',
    				muted: 'hsl(var(--automl-muted) / <alpha-value>)',
    				'muted-strong': 'hsl(var(--automl-muted-strong) / <alpha-value>)',
    				blue: 'hsl(var(--automl-blue) / <alpha-value>)',
    				'blue-hover': 'hsl(var(--automl-blue-hover) / <alpha-value>)',
    				'blue-soft': 'hsl(var(--automl-blue-soft) / <alpha-value>)',
    				'orange-soft': 'hsl(var(--automl-orange-soft) / <alpha-value>)',
    				orange: 'hsl(var(--automl-orange) / <alpha-value>)',
    				'cyan-soft': 'hsl(var(--automl-cyan-soft) / <alpha-value>)',
    				'green-soft': 'hsl(var(--automl-green-soft) / <alpha-value>)',
    				green: 'hsl(var(--automl-green) / <alpha-value>)',
    				lavender: 'hsl(var(--automl-lavender) / <alpha-value>)',
    				navy: 'hsl(var(--automl-navy) / <alpha-value>)',
    				'navy-soft': 'hsl(var(--automl-navy-soft) / <alpha-value>)'
    			}
    		}
    	}
    },
	plugins: ["tailwindcss-animated", "tailwindcss-animate", require("tailwindcss-animate")]
}
