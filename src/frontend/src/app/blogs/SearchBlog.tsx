import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import React, { useState } from "react";

interface SearchBlogProps {
  posts: IPost[];
  setDisplayedPosts: React.Dispatch<React.SetStateAction<IPost[]>>;
}

const SearchBlog: React.FC<SearchBlogProps> = ({
  posts,
  setDisplayedPosts,
}) => {
  const [searchTerm, setSearchTerm] = useState<string>("");

  const handleSearchPost = () => {
    // hiển thị toàn bộ bài viết nếu từ khóa rỗng
    if (!searchTerm) {
      setDisplayedPosts(posts);
      return;
    }

    // lọc bài viết dựa trên title chứa từ khóa
    const filteredPosts = posts.filter((post) =>
      post.title.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setDisplayedPosts(filteredPosts);
  };

  return (
    <div className="flex w-full max-w-sm items-center space-x-2 mx-auto">
      <Input
        type="email"
        placeholder="Search by title"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
      />
      <Button type="submit" onClick={() => handleSearchPost()}>
        Search
      </Button>
    </div>
  );
};

export default SearchBlog;
