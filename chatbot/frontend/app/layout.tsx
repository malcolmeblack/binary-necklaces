import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Binary Necklace Chat",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html>
      <head>
        <style>{`
          @font-face {
            font-family: 'CMSroman';
            src: url('/binary-necklaces/chatbot/cmunrm.ttf');
          }
          @font-face {
            font-family: 'CMSbold';
            src: url('/binary-necklaces/chatbot/cmunbx.ttf');
            font-weight: bold;
          }
          @font-face {
            font-family: 'CMSitalic';
            src: url('/binary-necklaces/chatbot/cmunti.ttf');
            font-weight: italic;
          }
          @font-face {
            font-family: jsMath;
            src: url('/binary-necklaces/chatbot/jsMath-cmsy10.ttf');
          }
          body {
            background-color: #000000;
            color: #ffffff;
            margin: 0;
            padding: 0;
			font-size: 18px;
          }
          a {
            color: #4da6ff;
          }
          button {
            background-color: #333333;
            color: #ffffff;
            border: 1px solid #666666;
            padding: 8px 16px;
			font-size: 18px;
            cursor: pointer;
            border-radius: 4px;
          }
          button:hover {
            background-color: #555555;
          }
          input, textarea {
            background-color: #1a1a1a;
            color: #ffffff;
            border: none;
            padding: 8px;
			font-size: 18px;
          }
        `}</style>
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}