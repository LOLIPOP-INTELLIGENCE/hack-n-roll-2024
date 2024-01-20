const { GoogleGenerativeAI } = require("@google/generative-ai");

// Access your API key as an environment variable (see "Set up your API key" above)
const genAI = new GoogleGenerativeAI("AIzaSyA9rnUXpz3roR-Pk7PCZezo8j558I7dJv8");

const fs = require("fs");

// Converts local file information to a GoogleGenerativeAI.Part object.
function fileToGenerativePart(path, mimeType) {
  return {
    inlineData: {
      data: Buffer.from(fs.readFileSync(path)).toString("base64"),
      mimeType
    },
  };
}

async function run() {
  // For text-and-image input (multimodal), use the gemini-pro-vision model
  const model = genAI.getGenerativeModel({ model: "gemini-pro-vision" });

  const prompt = "what is the expiry date?";

  const imageParts = [
    fileToGenerativePart("label.png", "image/png"),
  ];

  console.time("Response Time");

  const result = await model.generateContentStream([prompt, ...imageParts]);
  let text = '';
  for await (const chunk of result.stream) {
    const chunkText = chunk.text();
    console.log(chunkText);
    console.timeEnd("Response Time");
    text += chunkText;
  }  

//   const response = await result.response;
//   const text = response.text();
//   console.log(text);
}

run();