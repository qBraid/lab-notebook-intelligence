// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

const MonacoWebpackPlugin = require('monaco-editor-webpack-plugin');

module.exports = {
  plugins: [
    new MonacoWebpackPlugin({
      languages: ['python']
    })
  ],
  experiments: {
    syncWebAssembly: true
  }
};
