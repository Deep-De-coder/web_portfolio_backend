const express = require('express');
const app = express();
const port = process.env.PORT || 4000; // Render assigns a dynamic port

app.get('/', (req, res) => {
  res.send('Hello World! Server is running.');
});

app.listen(port, () => {
  console.log(`Server is listening on port ${port}`);
});
