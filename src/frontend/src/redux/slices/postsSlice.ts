import axios from "axios";
import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";

const POSTS_URL = "https://jsonplaceholder.typicode.com/posts";

interface PostState {
  posts: IPost[];
  status: "idle" | "loading" | "succeeded" | "failed";
  error: string | null;
}

const initialState: PostState = {
  posts: [],
  status: "idle",
  error: null,
};

export const fetchPostsAsync = createAsyncThunk(
  "posts/fetchPosts",
  async () => {
    const response = await axios.get(POSTS_URL);
    return response.data;
  }
);

export const addPostAsync = createAsyncThunk(
  "posts/addPost",
  async (newPost: Omit<IPost, "id">) => {
    const response = await axios.post(POSTS_URL, newPost);
    return response.data;
  }
);

export const updatePostAsync = createAsyncThunk(
  "posts/updatePost",
  async (updatedPost: IPost) => {
    const response = await axios.put(
      `${POSTS_URL}/${updatedPost.id}`,
      updatedPost
    );
    return response.data;
  }
);

export const deletePostAsync = createAsyncThunk(
  "posts/deletePost",
  async (id: string) => {
    const response = await axios.delete(`${POSTS_URL}/${id}`);
    return id;
  }
);

const postsSlice = createSlice({
  name: "posts",
  initialState,
  reducers: {
    addPost: (state, action: PayloadAction<IPost>) => {
      const { userId, id, title, body } = action.payload;
      state.posts.push({ userId, id, title, body });
    },
    deletePost: (state, action: PayloadAction<string>) => {
      const postId = action.payload;
      state.posts = state.posts.filter((post) => post.id !== postId);
    },
    editPost: (state, action: PayloadAction<IPost>) => {
      const { id, title, body } = action.payload;
      const postUpdate = state.posts.find((post) => post.id === id);
      if (postUpdate) {
        postUpdate.title = title;
        postUpdate.body = body;
      }
    },
  },
  extraReducers(builder) {
    builder
      .addCase(fetchPostsAsync.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(
        fetchPostsAsync.fulfilled,
        (state, action: PayloadAction<IPost[]>) => {
          state.status = "succeeded";
          state.posts = action.payload;
        }
      )
      .addCase(fetchPostsAsync.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.error?.message ?? "Failed to fetch posts";
      })
      .addCase(updatePostAsync.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(updatePostAsync.fulfilled, (state, action) => {
        const updatedPost = action.payload;
        const findPost = state.posts.find((post) => post.id === updatedPost.id);

        if (findPost) {
          findPost.title = updatedPost.title;
          findPost.body = updatedPost.body;
        }
        state.status = "succeeded";
      })
      .addCase(updatePostAsync.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.error?.message ?? "Failed to edit posts";
      })
      .addCase(deletePostAsync.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(
        deletePostAsync.fulfilled,
        (state, action: PayloadAction<string>) => {
          const postId = action.payload;
          state.posts = state.posts.filter((post) => post.id !== postId);
          state.status = "succeeded";
        }
      )
      .addCase(deletePostAsync.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.error?.message ?? "Failed to delete post";
      })
      .addCase(addPostAsync.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(
        addPostAsync.fulfilled,
        (state, action: PayloadAction<IPost>) => {
          state.posts.push(action.payload);
          state.status = "succeeded";
        }
      )
      .addCase(addPostAsync.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.error?.message ?? "Failed to add post";
      });
  },
});

export const selectAllPosts = (state: { posts: PostState }) =>
  state.posts.posts;
export const getPostsStatus = (state: { posts: PostState }) =>
  state.posts.status;
export const getPostsError = (state: { posts: PostState }) => state.posts.error;

export const { addPost, deletePost, editPost } = postsSlice.actions;

export default postsSlice.reducer;
