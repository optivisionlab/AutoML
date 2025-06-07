# Download and install nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash

# in lieu of restarting the shell
\. "$HOME/.nvm/nvm.sh"

# Download and install Node.js:
nvm install 20

# Verify the Node.js version:
node -v # Should print "v20.19.2".
nvm current # Should print "v20.19.2".

# Verify npm version:
npm -v # Should print "10.8.2".

npm audit fix --force
npm i --force
npm install tailwindcss@3.4.17 @tailwindcss/postcss@4.1.8 postcss@8.5.4
npx shadcn@2.6.0 init -y